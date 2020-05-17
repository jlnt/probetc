#!/usr/bin/env python3
#
# Originally forked from py-tc-probe by:
#   Scot Spinner (Scot.spinner@gmail.com) for AirJaldi
#   date: Mar 23, 2011
#
# pylint: disable=c-extension-no-member,missing-docstring,fixme

import getopt
import os
import subprocess
import sys
import threading
import time
import unittest

import rrdtool

TC_PATH = "/sbin/tc"
# Tip: to make sure you have ingress as well as egress graphed, use something
# like "tc qdisc add dev <your_ethernet_device> handle ffff: ingress"
DEFAULT_DEV = "eth4"
WORKING_PATH = "/var/www/probetc/"
# How often (in seconds) are we collecting data
COLLECTION_STEP = 5
# Colors choices for lines on a graph
GRAPH_COLOR = ['#000000', '#FF0000', '#00FF00', '#005555', '#FFFF00']

# Possible time windows for our graph
# When graphig all data source for one queue, we only use the first time
# window in this list.
# When graphing all queues on one data source, we choose appropriate
# time windows based on 'max_time_window' in DATA_SOURCES.
GRAPH_TIMES = [
    [3600, 'hourly'],
    [3600 * 24, 'daily'],
    [3600 * 24 * 7, 'weekly'],
    [3600 * 24 * 7 * 4, 'monthly'],
    [3600 * 24 * 7 * 52, 'yearly'],
]

# Data sources to put in our RRDs
# Each corresponds to data returned by tc
#
# Each data source will be graphed in all time windows
# until the index in 'max_time_window' excluded.
DATA_SOURCES = {
    'bytes_sent': {
        'max_time_window': 5,
        'unit': 'B/s'
    },
    'packets_sent': {
        'max_time_window': 1,
        'unit': 'pkt/s'
    },
    'dropped': {
        'max_time_window': 1,
        'unit': 'pkt/s'
    },
    'overlimits': {
        'max_time_window': 1,
        'unit': 'pkt/s'
    },
    'requeues': {
        'max_time_window': 1,
        'unit': 'pkt/s'
    },
}

RRD_LOCK = threading.Lock()


def write_html_files(qdisc_info):
    with open(WORKING_PATH + 'index.html', 'w') as index_html:
        html_string = (
            '<html>\n'
            '<head>\n'
            '</head>\n'
            '<body>\n'
            '<a href="type.html">view graphs by type of data</a><br>\n'
            '<a href="queue.html">view graphs by queue</a><br>\n'
            '</body>\n'
            '</html>')

        index_html.write(html_string)

    with open(WORKING_PATH + 'queue.html', 'w') as queue_html:
        html_string = ('<html>\n'
                       '<!-- This was created by py-tc-probe -->\n'
                       '<head>\n'
                       '<script type="text/javascript">\n'
                       'function reloadPage(){\n'
                       '    window.location.reload();\n'
                       '    delayFunc();\n'
                       '}\n'
                       'function delayFunc(){\n'
                       '    setTimeout("reloadPage()", 5000);\n'
                       '}\n'
                       '</script>\n'
                       '<style>\n'
                       'img {\n'
                       '  width: auto;\n'
                       '  height: 100%;\n'
                       '}\n'
                       '</style>\n'
                       '</head>\n'
                       '<body onload="delayFunc()">')

        for graph in qdisc_info:
            html_string += '<img src="' + graph['name'] + '.png"><br>\n'
        html_string += '</body></html>'
        queue_html.write(html_string)

    with open(WORKING_PATH + 'type.html', 'w') as type_html:
        html_string = ('<html>\n'
                       '<!-- This was created by py-tc-probe -->\n'
                       '<head>\n'
                       '<style>\n'
                       'img {\n'
                       '  max-width: 100%;\n'
                       '  height: auto;\n'
                       '}\n'
                       '</style>\n'
                       '<script type="text/javascript">\n'
                       'function reloadPage(){\n'
                       '    window.location.reload();\n'
                       '    delayFunc();\n'
                       '}\n'
                       'function delayFunc(){\n'
                       '    setTimeout("reloadPage()", 5000);\n'
                       '}\n'
                       '</script>\n'
                       '</head>\n'
                       '<body onload="delayFunc()">\n')
        html_img = list()
        for data_source, graph_info in DATA_SOURCES.items():

            time_slice = slice(0, graph_info['max_time_window'])
            for _, period_name in GRAPH_TIMES[time_slice]:
                file_suffix = '-' + period_name
                html_img.append('<img src="' + data_source + file_suffix +
                                '.png"><br>\n')

        html_string += ''.join(html_img)
        html_string += '</body>\n</html>'
        type_html.write(html_string)


class QdiscData:
    # pylint: disable=too-many-instance-attributes,too-few-public-methods

    def __init__(self, tc_qdisc_string):
        qdisc_lines = tc_qdisc_string.split("\n")
        #there are three lines...
        name_line = qdisc_lines[0].split(" ")
        stats_line = qdisc_lines[1].split(" ")
        # rateLine = stringLine[2].split(" ")

        self.queue_type = name_line[1]
        self.queue_name = name_line[2].replace(':', '-')
        self.root_or_parent = name_line[3]

        self.sent_bytes = stats_line[2]
        self.sent_packets = stats_line[4]
        self.dropped = stats_line[7].rstrip(",")
        self.overlimits = stats_line[9]
        self.requeues = stats_line[11].rstrip(")")


class TestQdiscData(unittest.TestCase):
    tc_qdisc_string = (
        " htb 1: root refcnt 2 r2q 10 default 1 direct_packets_stat 0 direct_qlen 1000\n"
        " Sent 36183382311 bytes 91256169 pkt (dropped 18512, overlimits 12565189 requeues 47) \n"
        " backlog 0b 0p requeues 47\n")

    def test_parsing(self):
        qdisc_data = QdiscData(self.tc_qdisc_string)

        self.assertEqual(qdisc_data.queue_type, "htb")
        self.assertEqual(qdisc_data.queue_name, "1-")
        self.assertEqual(qdisc_data.root_or_parent, "root")

        self.assertEqual(qdisc_data.sent_bytes, '36183382311')
        self.assertEqual(qdisc_data.sent_packets, '91256169')
        self.assertEqual(qdisc_data.dropped, '18512')
        self.assertEqual(qdisc_data.overlimits, '12565189')
        self.assertEqual(qdisc_data.requeues, '47')


# Returns a list of outputs, one per qdisc. Suitable for QdiscData().
def get_tc_output():
    tc_output = subprocess.check_output(
        [TC_PATH, "-s", "qdisc", "show", "dev", DEFAULT_DEV])
    tc_qdisc_strings = tc_output.decode("utf-8").split("qdisc")
    tc_qdisc_strings.pop(0)
    return tc_qdisc_strings


def populate_qdiscs():
    qdisc_info = list()
    for qdisc_string in get_tc_output():
        qdisc_data = QdiscData(qdisc_string)
        qdisc_info.append({
            'name': qdisc_data.queue_name,
            'type': qdisc_data.queue_type,
            'root_or_parent': qdisc_data.root_or_parent
        })
    return qdisc_info


def create_rrd(qdisc_info):
    """ Create one RRD database per queue """
    for qdisc in qdisc_info:
        rrd_file_name = WORKING_PATH + qdisc['name'] + ".rrd"
        # --source tries to re-use the data from an existing database if there is one
        rrdtool.create(
            rrd_file_name,
            '--no-overwrite',
            '--step',
            str(COLLECTION_STEP),
            'DS:packets_sent:COUNTER:10:U:U',
            'DS:bytes_sent:COUNTER:10:U:U',
            'DS:dropped:COUNTER:10:U:U',
            'DS:overlimits:COUNTER:10:U:U',
            'DS:requeues:COUNTER:10:U:U',
            'RRA:AVERAGE:0.5:1:2h',  # Keep highest precision for 2h
            'RRA:AVERAGE:0.5:30s:2d',
            'RRA:AVERAGE:0.5:5m:1w',
            'RRA:AVERAGE:0.5:1h:1M',
            'RRA:AVERAGE:0.5:1d:5y',
        )


def update_rrd():
    # TODO: Capture time right after calling tc and use it instead of 'N:'
    for qdisc_string in get_tc_output():
        qdisc_data = QdiscData(qdisc_string)

        rrd_file_name = WORKING_PATH + qdisc_data.queue_name + ".rrd"
        values = ''.join((qdisc_data.sent_packets, ":", qdisc_data.sent_bytes,
                          ':', qdisc_data.dropped, ":", qdisc_data.overlimits,
                          ":", qdisc_data.requeues))
        RRD_LOCK.acquire()
        rrdtool.update(rrd_file_name, 'N:' + values)
        RRD_LOCK.release()


def make_graph(graph_file_base, graph_title, graph_definition, time_window_sec,
               units):
    graph_file_name = WORKING_PATH + graph_file_base + ".png"
    init_vars = [
        graph_file_name + '.tmp', '--width', '1920', '--height', '1080',
        '--full-size-mode', '--end', 'now', '--start',
        'end-' + str(time_window_sec) + 's', '--step',
        str(time_window_sec // 256), '--title', graph_title, '--vertical-label',
        units, '--lazy', '--font', 'TITLE:18', '--font', 'LEGEND:14', '--font',
        'AXIS:12'
    ]
    init_vars.extend(graph_definition)

    # This produces better error messages than the in-process graph() function
    # which just segfaults.
    # Also the in-process graph() function seems to have leaks and ends up
    # crashing.
    #
    init_vars.insert(0, "graph")
    init_vars.insert(0, "rrdtool")

    RRD_LOCK.acquire()
    subprocess.run(init_vars, stdout=subprocess.DEVNULL, check=True)
    #rrdtool.graph(*init_vars)
    RRD_LOCK.release()

    # Atomically replace the image.
    os.rename(graph_file_name + '.tmp', graph_file_name)


# pylint: disable=too-many-arguments
def generate_one_graph_line(rrd_file_name, data_source, line_id, line_legend,
                            line_style, color, units):
    def_string = [
        'DEF:' + line_id + '=' + rrd_file_name + ':' + data_source + ':AVERAGE'
    ]

    def_string.extend([
        line_style + line_id + color + ':' + line_legend,
        'VDEF:' + line_id + 'avg=' + line_id + ',AVERAGE',
        'VDEF:' + line_id + 'tot=' + line_id + ',TOTAL',
        'VDEF:' + line_id + 'min=' + line_id + ',MINIMUM',
        'VDEF:' + line_id + 'max=' + line_id + ',MAXIMUM',
        'VDEF:' + line_id + 'cur=' + line_id + ',LAST',
        'GPRINT:' + line_id + 'avg:Avg\\:%5.2lf%s' + units,
        'GPRINT:' + line_id + 'tot:Tot\\:%5.2lf%s',
        'GPRINT:' + line_id + 'min:Min\\:%5.2lf%s' + units,
        'GPRINT:' + line_id + 'max:Max\\:%5.2lf%s' + units,
        'GPRINT:' + line_id + 'cur:Cur\\:%5.2lf%s' + units,
    ])

    return def_string


def graph_queues(qdisc_info, iterations):
    """Graph all queues from their specific databases"""
    time_window_sec = GRAPH_TIMES[0][0]

    # Would we update more than ~1% of the graph?
    if iterations % (time_window_sec // (100 * COLLECTION_STEP)) != 0:
        return
    for qdisc in qdisc_info:
        rrd_file_name = WORKING_PATH + qdisc['name'] + ".rrd"
        graph_name = qdisc['type'] + ' ' + qdisc['name']
        units = 'pkt/s'

        graph_definition = list()

        # pylint: disable=bad-continuation
        for index, data_source in enumerate(
            ['packets_sent', 'dropped', 'overlimits', 'requeues']):
            new_def = generate_one_graph_line(rrd_file_name, data_source,
                                              data_source, data_source,
                                              'LINE1:', GRAPH_COLOR[index],
                                              units)
            graph_definition.extend(new_def)

        make_graph(qdisc['name'], graph_name, graph_definition, time_window_sec,
                   units)


def generate_graph_definition(qdisc_info, data_source, units):
    """Generate a graph definition for data_source taken from all qdiscs in
       |qdisc_info|. |data_source| is qdisc data returned to us by tc that
       is a DS in our RRD.
       The generated graph will be a superposition of the relevant |data_source|
       graph for all qdiscs.
    """

    def_string = list()

    for index, qdisc in enumerate(qdisc_info):
        if qdisc['root_or_parent'] == 'root':
            line_style = 'AREA:'
        else:
            line_style = 'LINE1:'

        line_id = qdisc['name']
        rrd_file_name = WORKING_PATH + qdisc['name'] + ".rrd"
        line_legend = qdisc['type'] + ' ' + qdisc['name']

        new_def = generate_one_graph_line(rrd_file_name, data_source, line_id,
                                          line_legend, line_style,
                                          GRAPH_COLOR[index], units)
        def_string.extend(new_def)

    return def_string


def graph_types(qdisc_info, iterations, verbose):
    """ Create one set of graphs per data source with all the qdiscs from
        qdisc_info on each graph.
        Only graph if iterations indicates that more than ~1% of the graph
        would be updated.
    """

    for data_source, graph_info in DATA_SOURCES.items():

        units = graph_info['unit']
        graph_definition = generate_graph_definition(qdisc_info, data_source,
                                                     units)

        time_slice = slice(0, graph_info['max_time_window'])
        for time_in_sec, period_name in GRAPH_TIMES[time_slice]:
            file_suffix = '-' + period_name
            # We update roughly if at least 1% of the graph would change
            # We are called every COLLECTION_STEP seconds
            # '//' is integer division
            if iterations % (time_in_sec // (100 * COLLECTION_STEP)) == 0:
                if verbose:
                    print("Updating " + data_source + ' (' + period_name + ')')
                make_graph(data_source + file_suffix,
                           data_source + ' ' + period_name, graph_definition,
                           time_in_sec, units)


def update_rrd_loop():
    while True:
        update_rrd()
        time.sleep(COLLECTION_STEP)


def usage():
    print("Usage: " + sys.argv[0] +
          " [-h, --help] [-v, --verbose], [-u --update]\n")
    sys.exit()


def parse_command_line():
    start_new = True
    verbose = False

    try:
        # pylint: disable=bad-continuation
        opts, _ = getopt.getopt(sys.argv[1:], 'huv',
                                ['help', 'update', 'verbose'])
    except getopt.GetoptError as err:
        print(err)
        usage()
        sys.exit(1)

    for o, _ in opts:  # pylint: disable=invalid-name
        if o in ('-u', '--update'):
            start_new = False
        elif o in ('-h', '--help'):
            usage()
            sys.exit()
        elif o in ('-v', '--verbose'):
            verbose = True
        else:
            usage()
            sys.exit()

    return start_new, verbose


def main():

    start_new, verbose = parse_command_line()

    qdisc_info = populate_qdiscs()

    if start_new:
        print("Starting new database")
        create_rrd(qdisc_info)

    write_html_files(qdisc_info)

    # Update the RRD database in a separate thread to make sure updates are
    # regular and independant of graphing time.
    update_thread = threading.Thread(target=update_rrd_loop, daemon=True)
    update_thread.start()

    iterations = 0
    while True:
        if verbose:
            print("Iteration " + str(iterations))
        graph_types(qdisc_info, iterations, verbose)
        graph_queues(qdisc_info, iterations)
        if verbose:
            print("Done")
        time.sleep(COLLECTION_STEP)
        # Add an upper bound to |iterations|.
        iterations = (iterations + 1) % (1 << 20)


if __name__ == '__main__':
    main()
