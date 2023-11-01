"""This module defines all the routes for the filler-word removal server."""
import json
import os
import sys
import traceback

from quart_cors import cors

import quart

from config import ensure_dirs

from quart import Quart, request, jsonify

from media import save_uploaded_file, get_uploaded_file_paths
from store import Store, Sources, State
from daily import is_daily_supported

app = Quart(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1000000 * 600
cors(app, allow_origin="*", allow_headers=["content-type"])
ensure_dirs()

database = Store("all-hands", 13)


@app.before_serving
async def init():
    print("BEFORE SERVING")
    app.add_background_task(database.load_index)


@app.after_serving
async def shutdown():
    print("AFTER SERVING")
    for task in app.background_tasks:
        task.cancel()


@app.route('/status/capabilities', methods=['GET'])
def get_capabilities():
    print("Retrieving capabilities of vector store")
    daily_supported = is_daily_supported()
    return jsonify({
        "daily": daily_supported
    }), 200


@app.route('/status/db', methods=['GET'])
def get_db_status():
    return jsonify(database.status), 200


@app.route('/status/uploads', methods=['GET'])
def get_uploaded_files():
    try:
        file_paths = get_uploaded_file_paths()
        file_names = []
        # Return only the names, not paths on the server
        for path in file_paths:
            file_names.append(os.path.basename(path))
        return jsonify({
            "files": file_names
        }), 200
    except Exception as e:
        process_error("Failed to retrieve uploaded file paths", 500, e)


@app.route('/db/index', methods=['POST'])
async def init_or_update_store():
    print("Initializing or updating vector store")
    if database.status.state in [State.LOADING, State.CREATING, State.UPDATING]:
        process_error('Vector store not ready for further updates', 400)
    raw = await request.get_data()
    data = json.loads(raw or 'null')
    if data is None:
        return process_error(f"Must provide at least the 'source' property in request body", 400)

    index_source = None
    source = data["source"]
    if source == "daily":
        index_source = Sources.DAILY
        room_name = data["room_name"]
        if room_name:
            database.daily_room_name = room_name
        max_recordings = data["max_recordings"]
        if max_recordings:
            database.max_videos = int(max_recordings)
    elif source == "uploads":
        index_source = Sources.UPLOADS
    else:
        return process_error(f"Unrecognized source: {source}. Source must be 'daily' or 'uploads'", 400)
    try:
        app.add_background_task(database.initialize_or_update, index_source)
        return '', 200
    except Exception as e:
        return process_error('Failed to initialize database', 500, e)

@app.route('/upload', methods=['POST'])
async def upload_file():
    """Saves uploaded MP4 file and starts processing.
    Returns project ID"""
    files = await request.files
    try:
        file = files["file"]
    except Exception as e:
        return process_error("failed to retrieve file from request. Was a file provided?", 400, e)
    app.add_background_task(save_uploaded_file, file)
    return "{}", 200


@app.route('/db/query', methods=['POST'])
async def query_db():
    if not database.ready():
        return process_error("Vector index is not yet ready; try again later", 423)
    data = await request.get_json()
    print("raw:", data)

    query = data["query"]
    print("query:", query)
    try:
        res = database.query(query)
        answer = ""
        for response in res.response:
            if answer == "":
                answer += response
                continue
            answer += f". {response}"
        print("res:", res)
        return jsonify({
            "answer": answer,
            "metadata": res.metadata,
        }), 200
    except Exception as e:
        return process_error('failed to query index', 500, e)


def process_error(msg: str, code=500, error: Exception = None, ) -> tuple[quart.Response, int]:
    """Prints provided error and returns appropriately-formatted response."""
    if error:
        traceback.print_exc()
        print(msg, error, file=sys.stderr)
    response = {'error': msg}
    return jsonify(response), code

app.run()

if __name__ == '__main__':
    app.run(debug=True)
