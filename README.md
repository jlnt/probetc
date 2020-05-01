tcprobe is a small utility for Linux to graph network traffic using
[RRDtool](https://oss.oetiker.ch/rrdtool/).

It uses Linux' traffic control interface (via the "tc" tool) to get its data.
As such, it is suitable both for "plug and play" use cases (where one only
wants to see egress and ingress traffic), but also more advanced use cases
with multiple qdisc (queuing disciplines) used for traffic shaping and QoS.

Things are kept very simple: you should pretty much be able to run the tool and
start seeing traffic graphs in a web browser. Data will be collected in a
round-robin database for you and all graphs will be updated as needed
automatically.

tcprobe is written in Python 3. It was originally based on a tool called
py-tc-probe from Scot Spinner, although pretty much none of the original code
remains.
