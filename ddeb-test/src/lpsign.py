#!/usr/bin/python3
"""Pretend crypto for charm testing."""

import base64
import json
import random

import flask
import nacl.public
from nacl.encoding import Base64Encoder

app = flask.Flask("lpsign")
SERVICE_KEY = nacl.public.PrivateKey.generate()


@app.post("/nonce")
def nonce():
    """Generate a random string."""
    # TODO use ts in nonce
    word = base64.b64encode(random.randbytes(nacl.public.Box.NONCE_SIZE)).decode()
    return flask.jsonify({"nonce": word})


@app.get("/service-key")
def service_key():
    """Return service key."""
    encoded_key = SERVICE_KEY.public_key.encode(encoder=Base64Encoder).decode()
    return flask.jsonify({"service-key": encoded_key})


@app.post("/sign")
def sign():
    """Sign a payload."""
    headers = flask.request.headers
    client_pubkey = nacl.public.PublicKey(headers["X-Client-Public-Key"], encoder=Base64Encoder)
    nonce = base64.b64decode(headers["X-Nonce"])
    response_nonce = base64.b64decode(headers["X-Response-Nonce"])

    box = nacl.public.Box(SERVICE_KEY, client_pubkey)
    incoming = json.loads(
        box.decrypt(
            flask.request.get_data(),
            nonce,
            encoder=Base64Encoder,
        )
    )

    signed_message = base64.b64encode(
        b"-----BEGIN FAKE SIGNATURE-----\n"
        + base64.b64decode(incoming["message"])
        + b"\n-----END FAKE SIGNATURE-----\n"
    ).decode()

    response_data = box.encrypt(
        json.dumps({"signed-message": signed_message}).encode(),
        response_nonce,
    )[box.NONCE_SIZE :]
    return flask.Response(base64.b64encode(response_data), mimetype="application/x-boxed-json")


if __name__ == "__main__":
    app.run()
