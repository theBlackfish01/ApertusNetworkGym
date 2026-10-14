# Demo video: script and shot list (two minutes)

The video is the operator console on the laptop, live, with the model server up. Everything the
viewer sees is real: the readers and the decider answer on the laptop's GPU. Record the browser
at 1440 px wide or more, dark theme, no narration overlays needed beyond the spoken words.

**Set-up (before recording).** In WSL: the llama.cpp server with the four adapters (README,
"On a laptop"), then `uv run python src/console.py --base-url http://127.0.0.1:8089/v1
--no-arrivals`. Open http://127.0.0.1:8090, set the pace to 2 /s, switch "simulated operator"
off, leave "instructions with requests" on. In the Race view, prepare the race and run it to the
end (speed "fast", about a minute), then return to Operate. Have these lines ready to paste.

| Time | What the viewer sees | What you say |
| --- | --- | --- |
| 0:00–0:12 | The console, stream paused, the European network on the map, the feed empty but for "console ready". | "Operators of optical networks state policy in plain language. This is Apertus 8B reading that language, and a rule engine enforcing it, on my laptop." |
| 0:12–0:30 | Type the policy `für die nächsten 6 Stunden meiden 400G-Dienste die Strecke Zürich–Mailand` and press Read. The reading appears: read-back, scope rate:400, until 6 h, the TAPI constraint folded, the preview line. Click Add. The policy appears in the feed and in the rail with its remaining hours; the Zurich–Milan link turns red on the map. | "A standing policy, typed in German. Apertus translates it once into one line: avoid that link, only for 400 gigabit requests, for six hours. The console reads it back, previews it on a copy of the network, and shows it as the TAPI constraint a controller takes. I add it." |
| 0:30–0:50 | Press Play. Requests flow; the feed narrates: instruction with a request, readers agree, rule engine decides, routes draw in blue; a 400G request shows "#1" in the audit. | "Now the stream runs. Each request arrives with an instruction of its own, in one of four languages. Two readers translate it; when they agree, the rule engine decides under the policy and the instruction together, and the feed says who decided and whether the decision respects what was meant." |
| 0:50–1:15 | The stream pauses on a question: two readings side by side with the route each would take. Pick one. The stream resumes. | "Here the two readers disagree, and this request would be routed differently under the two readings, so the system stops and asks me, showing the consequence rather than the sentence. I choose. Asking only when it matters cut the questions by a sixth at the same error rate." |
| 1:15–1:35 | Type a second policy that conflicts: `until further notice, all traffic must pass through Frankfurt` (or the stored sentence). The reading shows an override or contradiction note. Add it. Both policies in the rail with their remaining hours. Play on; a request outside the language goes to the decider; the guard event appears if one occurs. | "A second policy. The console names the conflict with the first before I add it. An instruction the language cannot express goes to a fine-tuned decider, and a guard replaces its route if it breaks a constraint the line carries." |
| 1:35–1:50 | Click "inspect" on the last request: the five candidates, the constraint that dropped each, the spectrum the lightpath took. Close it; open the audit tab, then the policy report. | "Every lightpath can be opened: the five candidate paths and why each was kept or dropped. Every lightpath has an audit row, and every policy reports what it did." |
| 1:50–2:00 | Switch to Race: the four lanes on the evaluation's stream, run to the end before recording, each marked "the same as the stored evaluation run". | "On blind test sentences the reader is right on 95 %, its decisions comply on 99.6 %, and the policy table stays within 1.5 points of the truth in closed loop. On-premise, air-gapped, one laptop GPU." |

**If the server is not available for the recording:** run `make console` instead; the same
sequence works from recorded answers with the lines the command bar offers (pick them from the
list rather than typing new ones), and say "replayed from recorded answers" once. The Tour
(header) drives a similar sequence by itself, for a rehearsal.

**Cuts to avoid:** no scrolling through code; no terminal except, if wanted, two seconds of the
server starting. Keep the mouse still while speaking. Record the whole take, then trim.
