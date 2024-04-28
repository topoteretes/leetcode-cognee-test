## Continue dev + cognee RAG metrics


### Setup

mitmproxy is a python package, so you can install it with pip:

```bash
pip install mitmproxy
```

### Usage

To start mitmproxy, simply run:

```bash
mitmdump --mode reverse:http://localhost:11435 --flow-detail 4
```

This will start mitmproxy in reverse proxy mode, forwarding all incoming requests to `localhost:11435`. The `--flow-detail 4` flag will print detailed information about each request and response.

Make sure to run mockserver before running mitmproxy.

To start mockserver, simply run:

``` bash
pip install -r requirements.txt
```

```bash
python openapi_mock_server.py
```
It will store and write the manually made responses to the files.
This way we obtain the context made by continue.dev


To evaluate the RAG metrics, run:

```bash
python rag_metrics.py
```