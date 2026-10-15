# Demo video: script and shot list (two minutes)

The video is the operator console on the laptop, live, with the model server up. Everything the
viewer sees is real: the readers and the decider answer on the laptop's GPU. Record the browser
at 1440 px wide or more, dark theme, no narration overlays needed beyond the spoken words.

**Set-up (before recording).** In WSL: the llama.cpp server with the four adapters (the repository's README.md,
"On a laptop"), then `uv run python src/console.py --base-url http://127.0.0.1:8089/v1
--no-arrivals`. Open http://127.0.0.1:8090, set the pace to 2 /s, switch "simulated operator"
off, leave "instructions with requests" on. In the Race view, prepare the race and run it to the
end (speed "fast", about a minute), then return to Operate. Have these lines ready to paste.

| Time | What the viewer sees | What you say (short sentences, easy to say; 15 October) |
| --- | --- | --- |
| 0:00–0:12 | The console, stream paused, the European network on the map, the feed empty but for "console ready". | "Network operators set routing rules in plain language. Here, Apertus reads those rules, and a rule engine enforces them. All on my laptop." |
| 0:12–0:30 | Type the policy `für die nächsten 6 Stunden meiden 400G-Dienste die Strecke Zürich–Mailand` and press Read. The reading appears: read-back, scope rate:400, until 6 h, the TAPI constraint folded, the preview line. Click Add. The policy appears in the feed and in the rail with its remaining hours; the Zurich–Milan link turns red on the map. | "I type a rule in German. Apertus turns it into one line: avoid this link, only for 400G, for six hours. I check it, and add it." |
| 0:30–0:50 | Press Play. Requests flow; the feed narrates: instruction with a request, readers agree, rule engine decides, routes draw in blue; a 400G request shows "#1" in the audit. | "Now requests come in. Each one can carry its own instruction. Two readers translate it. If they agree, the rule engine decides." |
| 0:50–1:15 | The stream pauses on a question: two readings side by side with the route each would take. Pick one. The stream resumes. | "Here the two readers disagree, and that would change the route. So it stops and asks me. I pick one." |
| 1:15–1:35 | Type a second policy that conflicts: `until further notice, all traffic must pass through Frankfurt` (or the stored sentence). The reading shows an override or contradiction note. Add it. Both policies in the rail with their remaining hours. Play on; a request outside the language goes to the decider; the guard event appears if one occurs. | "A second rule. It warns me that it clashes with the first one. Anything the rules can't express goes to a second model, with a safety check." |
| 1:35–1:50 | Click "inspect" on the last request: the five candidates, the constraint that dropped each, the spectrum the lightpath took. Close it; open the audit tab, then the policy report. | "I can open any request and see why each route was kept or dropped." |
| 1:50–2:00 | Switch to Race: the four lanes on the evaluation's stream, run to the end before recording, each marked "the same as the stored evaluation run". | "On blind tests, it reads ninety-five percent of instructions correctly. And it runs offline, on one laptop." |

**If the server is not available for the recording:** run `make console` instead; the same
sequence works from recorded answers with the lines the command bar offers (pick them from the
list rather than typing new ones), and say "replayed from recorded answers" once. The Tour
(header) drives a similar sequence by itself, for a rehearsal.

**Cuts to avoid:** no scrolling through code; no terminal except, if wanted, two seconds of the
server starting. Keep the mouse still while speaking. Record the whole take, then trim.
