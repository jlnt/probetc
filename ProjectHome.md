# py-tc-probe #


---


**py-tc-probe** polls tc to create graphs, using rrdtool, that show the status of all the qdiscs on one interface.  It creates html files to view the graphs, with automatic refreshing using Java Script.  Currently it creates graphs in two ways: graph all statistics (packets sent, dropped, overlimits, requeued) for one qdisc on a single graph, and graph all statistics of a certain kind (eg. packets sent) for all qdiscs on one graph.

Please check out the source and tell me what you think!!