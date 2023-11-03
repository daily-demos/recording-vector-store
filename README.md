
## Vector store and query engine for video recordings

This demo helps you build a vector database using your recordings using LlamaIndex and Chroma.

## Running the demo locally

This demo was tested with Python version 3.11.6. We recommend running this in a virtual environment.

### Set up your environment

1. Clone this repository.
1. Copy the `.env.sample` file into `.env`. DO NOT submit your `.env` file to version control.
1. Specify your `OPENAI_API_KEY` in the `.env` file. This is required.
1. Optional: If you wish to use Deepgram instead of Whisper, paste your Deepgram API key into the `DEEPGRAM_API_KEY` environment variable in `.env`
1. Optional: If you wish to automatically retrieve Daily recordings for your domain instead of uploading an MP4 manually, paste your Daily API key into the `DAILY_API_KEY` environment variable in `.env`.

### Create and activate a virtual environment

In the root of the repository on your local machine, run the following commands:

1. `python3 -m venv venv`
1. `source venv/bin/activate`

### Run the application

In the virtual environment, run the following: 

1. Run `pip install -r requirements.txt` from the root directory of this repo on your local machine.
1. Run `quart --app server/index.py --debug run` in your terminal.
1. Run `python -m http.server --directory client` in another terminal window.

Now, open the localhost address shown in your terminal after the last step above. You should see the front-end of the demo allowing you to upload your MP4 files or populate the index by fetching your Daily recordings.

## How it works

The demo consists of a small JavaScript client and a Python server.

The user can create a new vector database or update one that already exists from Daily cloud recordings or manually-uploaded MP4 files.

The user can then query their database. After initial update, queries and updates can run at the same time.


## Transcribers 

The demo implements two transcription models to choose from:

1. Whisper. This is an implementation that does not depend on any third-party APIs. The whisper model of choice is downloaded to the machine running the server component.
2. Deepgram. If a Deepgram API key is specified in your local `.env` file, the server will use Deepgram's Nova-tier model to detect filler words.

More transcribers can be added by following the same interface as the above. Just place your implementation into `server/transcription/` and add your new transcriber to the `Transcribers` enum in `server/store.py`
