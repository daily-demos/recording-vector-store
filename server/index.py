"""This module defines all the routes for the filler-word removal server."""
import json
import sys
import traceback

from quart_cors import cors

import quart

from config import ensure_dirs

from quart import Quart, request, jsonify

from store import Store
from daily import is_daily_supported

app = Quart(__name__)
cors(app)
ensure_dirs()

database: Store = None

@app.before_serving
async def init():
    global database
    database = Store("all-hands", 13)


@app.after_serving
async def shutdown():
    for task in app.background_tasks:
        task.cancel()


@app.route('/db/status', methods=['GET'])
def get_db_status():
    print("Checking status of vector store:", database.status)
    return jsonify(database.status), 200


@app.route('/capabilities', methods=['GET'])
def get_capabilities():
    print("Retrieving capabilities of vector store")
    daily_supported = is_daily_supported()
    return jsonify({
        "daily": daily_supported
    }), 200


@app.route('/db/initialize', methods=['POST'])
async def initialize_db():
    print("Initializing or updating vector store")

    raw = await request.get_data()
    data = json.loads(raw or 'null')
    if data is not None:
        room_name = data["room_name"]
        if room_name:
            database.daily_room_name = room_name
        max_recordings = data["max_recordings"]
        if max_recordings:
            database.max_videos = int(max_recordings)
    try:
        app.add_background_task(database.initialize)
        return 200
    except Exception as e:
        return process_error('Failed to initialize database', e, 500)


@app.route('/query', methods=['POST'])
async def query_db():
    if not database.ready():
        return process_error("Vector index is not yet ready; try again later", None, 500)

    data = await request.get_json()
    print("raw:", data)

    query = data["query"]
    print("query:", query)
    try:
        res = database.query(query)

        print("res:", res)
        return jsonify({
            "answer": res.response.join('. '),
            "metadata": res.metadata,
        }), 200
    except Exception as e:
        return process_error('failed to query index', e, 500)


def process_error(msg: str, error: Exception, code) -> tuple[quart.Response, int]:
    """Prints provided error and returns appropriately-formatted response."""
    if error:
        traceback.print_exc()
        print(msg, error, file=sys.stderr)
    response = {'error': msg}
    return jsonify(response), code


app.run()

if __name__ == '__main__':
    app.run(debug=True)
