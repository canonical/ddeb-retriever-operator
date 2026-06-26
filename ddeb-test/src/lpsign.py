#!/usr/bin/python3
"""Pretend crypto for charm testing."""

import json
import random
from base64 import b64decode, b64encode

import flask
import nacl.public
from nacl.encoding import Base64Encoder

app = flask.Flask("lpsign")
SERVICE_KEY = nacl.public.PrivateKey.generate()


@app.post("/nonce")
def nonce():
    """Generate a random string."""
    # TODO use ts in nonce
    word = b64encode(random.randbytes(nacl.public.Box.NONCE_SIZE)).decode()
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
    client_pubkey = nacl.public.PublicKey(
        headers["X-Client-Public-Key"].encode(),
        encoder=Base64Encoder,
    )
    nonce = b64decode(headers["X-Nonce"])
    response_nonce = b64decode(headers["X-Response-Nonce"])

    box = nacl.public.Box(SERVICE_KEY, client_pubkey)
    incoming = json.loads(
        box.decrypt(
            flask.request.get_data(),
            nonce,
            encoder=Base64Encoder,
        )
    )
    mode = incoming.get("mode", "DETACHED")

    signed_message = b""
    if mode == "CLEAR":
        signed_message += b"-----BEGIN FAKE SIGNED MESSAGE-----\n"
        signed_message += b64decode(incoming["message"])
    signed_message += b"-----BEGIN FAKE SIGNATURE-----\nFAKE\n-----END FAKE SIGNATURE-----\n"

    response_data = box.encrypt(
        json.dumps({"signed-message": b64encode(signed_message).decode()}).encode(),
        response_nonce,
    )[box.NONCE_SIZE :]
    return flask.Response(b64encode(response_data), mimetype="application/x-boxed-json")


if __name__ == "__main__":
    app.run()
