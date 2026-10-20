# Run instructions

## Requirements

Python 3.9 or later. The Python programs use only the standard library; no additional Python packages need to be installed. The optional HTTP commands below also require `curl`; the live collector requires Bash.

Extract the code ZIP and run all commands below from its root directory.

## Task 1 — Run the prototype

```sh
python3 scraper.py --count 3
```

This uses the policy index URL supplied in the brief. The `--count` option accepts 3, 4 or 5.

To use an index hosted by your own local HTTP server instead:

```sh
python3 scraper.py --url http://localhost:3000/ --count 3
```

The local server must already be running at the specified URL.

## Run all offline tests

```sh
python3 -m unittest discover -s tests -v
```

These tests do not require network access.

## Task 3 — Run the failure demonstration only

```sh
python3 -m unittest discover -s tests -p test_scraper.py -k test_double_exposes_missing_format_validation -v
```

## Task 3 — Run the local HTTP fixtures

Start the windowed HTTP 429 fixture:

```sh
python3 task3/1/server_windowed_429.py --port 8000 --limit 3 --window 10
```

In another terminal, make four immediate local requests. The first three are allowed; the fourth returns HTTP 429 if all four arrive within the ten-second window:

```sh
for i in 1 2 3 4; do
  curl -i --max-time 5 http://127.0.0.1:8000/
done
```

After the recorded `Retry-After` delay, request the same URL again to check recovery. Press Ctrl+C in the server terminal to stop it. Restarting resets its state.

To run the separate persistent-counter fixture instead, stop the windowed server first, then run:

```sh
python3 task3/1/server.py
```

This server allows six PDF requests per process, then returns HTTP 429 for further PDF requests until restarted. Its `/slow.pdf` and `/hang.pdf` endpoints can be requested with a bounded client timeout:

```sh
curl -i --max-time 5 http://127.0.0.1:8000/slow.pdf
curl -i --max-time 5 http://127.0.0.1:8000/hang.pdf
```

Curl exit code 28 is expected for these timeout checks. Stop and restart the server to reset the counter between independent cases. Do not run both servers on the same port simultaneously.

## Optional — Recollect live rate-limit evidence

The saved responses are already included; rerunning the collector is not required for the offline checks. This command makes ten requests to the live policy website. Only run it when deliberately repeating the live experiment, not as part of the automated tests.

To save new responses in a fresh temporary directory without overwriting the submitted evidence:

```sh
script="$PWD/task3/2/rate_limit.sh"
output_dir="$(mktemp -d)"
(cd "$output_dir" && bash "$script")
printf 'Responses saved to %s\n' "$output_dir"
```
