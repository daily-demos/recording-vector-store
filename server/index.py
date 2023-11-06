"""This module defines all the routes for the filler-word removal server."""
import json
import os
import sys
import traceback

from quart_cors import cors
from quart import Quart, request, jsonify, Response

from config import ensure_dirs, get_third_party_config
from media import save_uploaded_file, get_uploaded_file_paths
from store import Store, Source, State

app = Quart(__name__)

# Allow uploads of up to 60MB by default.
app.config['MAX_CONTENT_LENGTH'] = 1000000 * 60

# Note that this is not a secure CORS configuration for production.
cors(app, allow_origin="*", allow_headers=["content-type"])
ensure_dirs()

api_config = get_third_party_config()
store = Store(api_config=api_config, max_videos=10)


@app.before_serving
async def init():
    """Initialize the index before serving"""
    # Start loading the index right away, in case one exists.
    app.add_background_task(store.load_index)


@app.after_serving
async def shutdown():
    """Stop all background tasks and threads"""

    # Note that any running thread pool workers finish
    # before shutdown is complete.
    store.destroy()
    for task in app.background_tasks:
        task.cancel()


#############################
# Server state-related routes
#############################

@app.route('/status/capabilities', methods=['GET'])
def get_capabilities():
    """Returns server capabilities, such as whether a Daily API key
    has been configured or not."""
    daily_supported = bool(api_config.daily_api_key)
    return jsonify({
        "daily": daily_supported
    }), 200


@app.route('/status/db', methods=['GET'])
def get_store_status():
    """Returns store status"""
    return jsonify(store.status), 200


@app.route('/status/uploads', methods=['GET'])
def get_uploaded_files():
    """Returns the file names of all files which are currently
    uploaded and pending indexing"""
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
        return process_error("Failed to retrieve uploaded file paths", 500, e)


#########################
# Database-related routes
#########################
@app.route('/db/index', methods=['POST'])
async def init_or_update_store():
    """Initializes a new vector store or update the existing store"""
    print("Initializing or updating vector store")

    # Only proceed if a store-update operation is not already taking place
    if store.status.state in [State.LOADING, State.CREATING, State.UPDATING]:
        return process_error('Vector store not ready for further updates', 400)
    raw = await request.get_data()
    data = json.loads(raw or 'null')
    if data is None:
        return process_error(
            "Must provide at least the 'source' property in request body", 400)

    # Check if user is updating index from Daily recordings or manual uploads
    source = data["source"]
    if source == "daily":
        index_source = Source.DAILY
        room_name = data["room_name"]
        if room_name:
            store.daily_room_name = room_name
        max_recordings = data["max_recordings"]
        if max_recordings:
            store.max_videos = int(max_recordings)
    elif source == "uploads":
        index_source = Source.UPLOADS
    else:
        return process_error(
            f"Unrecognized source: {source}. Source must be 'daily' or 'uploads'", 400)

    # Start updating the store
    app.add_background_task(store.initialize_or_update, index_source)
    return '', 200


@app.route('/db/query', methods=['POST'])
async def query_index():
    """Queries the loaded index"""
    if not store.ready():
        return process_error(
            "Vector index is not yet ready; try again later", 423)
    data = await request.get_json()
    query = data["query"]
    try:
        res = store.query(query)
        return jsonify({
            "answer": res.response,
        }), 200
    except Exception as e:
        return process_error('failed to query index', 500, e)


######################
# Manual upload routes
######################

@app.route('/upload', methods=['POST'])
async def upload_file():
    """Saves uploaded MP4 file and starts processing.
    Returns project ID"""
    files = await request.files
    try:
        file = files["file"]
    except Exception as e:
        return process_error(
            "failed to retrieve file from request. Was a file provided?", 400, e)
    app.add_background_task(save_uploaded_file, file)
    return "{}", 200


def process_error(msg: str, code=500, error: Exception = None,
                  ) -> tuple[Response, int]:
    """Prints provided error and returns appropriately-formatted response."""
    if error:
        traceback.print_exc()
        print(msg, error, file=sys.stderr)
    response = {'error': msg}
    return jsonify(response), code


app.run()

if __name__ == '__main__':
    app.run(debug=True)
