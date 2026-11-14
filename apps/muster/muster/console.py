"""Text-mode Muster for the UART console - the no-network fallback UI.

    python3 -m muster.console            # interactive: type a report, Enter to register
    python3 -m muster.console --watch    # read-only board, refreshes every 2 s

Talks to the running app on 127.0.0.1:8000 (same board), so it works with Wi-Fi off
and without any USB-C network link.
"""
import argparse
import json
import os
import sys
import time
import urllib.request

URL = os.getenv("MUSTER_URL", "http://127.0.0.1:8000")
C = {"RED": "\033[41;97m", "ORANGE": "\033[43;30m", "YELLOW": "\033[103;30m", "GREEN": "\033[42;30m"}
R, B, DIM, GRN = "\033[0m", "\033[1m", "\033[2m", "\033[32m"


def call(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(URL + path, data=data, headers={"Content-Type": "application/json"},
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}")


def render():
    b = call("/board")
    out = [f"{B}MUSTER{R}  site {b['site']}  [{b['mode']}]   people {b['people']}   "
           f"radio {b['uplink_bytes']} bytes   {DIM}(offline, on-device){R}", ""]
    for m in b["matches"]:
        out.append(f"{GRN}{B}POSSIBLE REUNION (staff to verify):{R} {m['name']}"
                   f"{', ' + str(m['age']) if m['age'] else ''} is here (#{m['found_in']}); "
                   f"#{m['missing_in']} is looking for them.")
    out.append(f"{B}PRIORITY QUEUE{R}")
    for r in b["records"]:
        i, p = r["intake"], r["triage"]["priority"]
        tags = i["medical_needs"] + i["injuries"] + [f"looking for {x['name']}" for x in i["missing"]] \
            + [f"brought {x['name']}" for x in i["found"]]
        out.append(f" {C.get(p, '')} {p:6} {R} #{r['id']:<3} {(i['speaker_name'] or 'Unnamed'):10} "
                   f"{i['language']}  grp {i['group_size']}  {', '.join(tags)}")
    if b["needs"]:
        out.append(f"\n{B}SUPPLIES{R}  " + "  ".join(f"{k}:{v}" for k, v in b["needs"].items()))
    out.append(f"\n{B}RADIO UPLINK{R}")
    out += [f"  {GRN}{r['uplink']}{R} {DIM}({len(r['uplink'])}B){R}" for r in b["records"][-5:]]
    out.append(f"\n{B}DECISION LOG{R}")
    for e in call("/log")[-6:]:
        what = e.get("error") or e.get("action") or e.get("priority") or e.get("backend") or ""
        ms = f"{e['ms']}ms" if "ms" in e else ""
        out.append(f"  {DIM}{e['t']}{R} {e['stage']:8} {ms:>9} {what}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--watch", action="store_true")
    a = ap.parse_args()
    if a.watch:
        while True:
            sys.stdout.write("\033[2J\033[H" + render() + "\n")
            sys.stdout.flush()
            time.sleep(2)
    print(render())
    while True:
        try:
            text = input(f"\n{B}report>{R} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not text:
            continue
        if text == "/reset":
            call("/reset", {})
        else:
            t0 = time.time()
            d = call("/intake", {"text": text})
            if "record" in d:
                r = d["record"]
                print(f"  -> {r['triage']['priority']}  #{r['id']}  ({time.time() - t0:.1f}s)  reply: {r['reply']}")
            else:
                print(f"  ERROR {d.get('error')}")
        print("\n" + render())


if __name__ == "__main__":
    main()
