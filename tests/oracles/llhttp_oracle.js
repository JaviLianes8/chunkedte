// Decode chunked bodies with the llhttp parser built into Node.js, as an independent oracle.
//
// Reads one hex-encoded chunked body per stdin line and prints one JSON line per body:
// {"ok": true, "body": hex, "trailers": [[name, value], ...], "used": n} when llhttp
// completes the message after `used` bytes of the body, or {"ok": false, "code": "HPE_..."}.
// Each body follows the header section of a POST request with Transfer-Encoding: chunked,
// and is fed one byte at a time so the end of the message is known to the byte.
"use strict";

const { HTTPParser } = require("_http_common");
const readline = require("readline");

const HEAD = Buffer.from("POST / HTTP/1.1\r\nHost: a\r\nTransfer-Encoding: chunked\r\n\r\n");

function run(body) {
  const parser = new HTTPParser();
  parser.initialize(HTTPParser.REQUEST, {});
  const pieces = [];
  let headerCount = -1;
  let trailers = [];
  let done = false;
  parser[HTTPParser.kOnHeadersComplete] = (major, minor, headers) => {
    headerCount = headers ? headers.length : 0;
    return 0;
  };
  parser[HTTPParser.kOnHeaders] = (headers) => {
    trailers = trailers.concat(headers);
  };
  parser[HTTPParser.kOnBody] = (chunk) => pieces.push(Buffer.from(chunk));
  parser[HTTPParser.kOnMessageComplete] = () => {
    done = true;
  };
  const head = parser.execute(HEAD);
  if (head instanceof Error) {
    return { ok: false, code: "HEAD " + head.code };
  }
  for (let at = 0; at < body.length; at++) {
    const result = parser.execute(body.subarray(at, at + 1));
    if (result instanceof Error) {
      return { ok: false, code: result.code };
    }
    if (done) {
      const pairs = [];
      for (let i = 0; i < trailers.length; i += 2) {
        pairs.push([trailers[i], trailers[i + 1]]);
      }
      return { ok: true, body: Buffer.concat(pieces).toString("hex"), trailers: pairs, used: at + 1 };
    }
  }
  return { ok: false, code: "INCOMPLETE" };
}

const lines = readline.createInterface({ input: process.stdin });
lines.on("line", (line) => {
  process.stdout.write(JSON.stringify(run(Buffer.from(line.trim(), "hex"))) + "\n");
});
