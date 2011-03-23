import time
import subprocess
import sys
sys.path.append('/usr/lib/pymodules/python2.6/')
import rrdtool, tempfile
#################################################################
#
#	author: Scot Spinner (Scot.spinner@gmail.com) for AirJaldi
#	date: Mar 23, 2011
#
#################################################################

#this requires python 2.7+ which needs to be downloaded and compiled
#also need some rrdtool python package

tcPath = "/sbin/tc"
defaultDev = "eth1"
workingPath = "/var/www/probetc/"
graphTimeWindowSec = 3600
nameArray = list()

def writeHtmlFiles():
    with open(workingPath + 'index.html', 'w') as indexHtml:
        htmlString = '<html>\
<head>\
</head>\
<body>\
<a href="type.html">view graphs by type of data</a><br>\
<a href="queue.html">view graphs by queue</a><br>\
</body>\
</html>'
        indexHtml.write(htmlString)

    with open(workingPath + 'queue.html', 'w') as queueHtml:
        htmlString = '<html>\
<!-- This was created by py-tc-probe -->\
<head>\
<script type="text/javascript">\
function reloadPage(){\
    window.location.reload();\
    delayFunc();\
}\
function delayFunc(){\
    setTimeout("reloadPage()", 5000);\
}\
</script>\
</head>\
<body onload="delayFunc()">'
        for graph in nameArray:
            htmlString += '<img src="' + graph['name'] + '.png"><br>\n'
        htmlString += '</body></html>'
        queueHtml.write(htmlString)

    with open(workingPath + 'type.html', 'w') as typeHtml:
        htmlString = '<html>\
<!-- This was created by py-tc-probe -->\
<head>\
<script type="text/javascript">\
function reloadPage(){\
    window.location.reload();\
    delayFunc();\
}\
function delayFunc(){\
    setTimeout("reloadPage()", 5000);\
}\
</script>\
</head>\
<body onload="delayFunc()">\
<img src="bytesSent.png"><br>\
<img src="packetSent.png"><br>\
<img src="dropped.png"><br>\
<img src="requeues.png"><br>\
<img src="overlimits.png"><br>\
</body>\
</html>'
        typeHtml.write(htmlString)

def updateRRD():
    tcReturnVal = subprocess.check_output([tcPath, "-s", "qdisc", "show", "dev", defaultDev])

    splitString = tcReturnVal.split("qdisc")
    splitString.pop(0)

    for x in splitString:
        stringLine = x.split("\n")
                #there are three lines...
        nameLine = stringLine[0].split(" ")
        statsLine = stringLine[1].split(" ")
        rateLine = stringLine[2].split(" ")

        queueName = nameLine[2]
        queueType = nameLine[1]
        sentBytes = statsLine[2]
        sentPackets = statsLine[4]
        dropped = statsLine[7].rstrip(",")
        overlimits = statsLine[9]
        requeues = statsLine[11].rstrip(")")

        rrdFileName = (workingPath + queueName + ".rrd").replace(":","-")
        values = sentPackets + ":" + sentBytes + ':' + dropped + ":" + overlimits + ":" + requeues
        rrdtool.update(rrdFileName, 'N:' + values)

        graphFileName = (workingPath + queueName + ".png").replace(":","-")

        rrdtool.graph(graphFileName,
            '--width', '800',
            '--height', '400',
            '--end', 'now', '--start', 'end-' + str(graphTimeWindowSec) + 's',
            '--vertical-label', 'pkt/s', '--title', queueType + ' ' + queueName,
            'DEF:packetSent=' + rrdFileName + ':packetSent:AVERAGE',
            'DEF:dropped=' + rrdFileName + ':dropped:AVERAGE',
            'DEF:overlimits=' + rrdFileName + ':overlimits:AVERAGE',
            'DEF:requeues=' + rrdFileName + ':requeues:AVERAGE',
            'LINE1:packetSent#000000:Packets Sent',
            'LINE1:dropped#FF0000:Dropped Packets',
            'LINE1:overlimits#0000FF:overlimit Packets',
            'LINE1:requeues#550055:requeues')


def createRRD():
    global nameArray
    tcReturnVal = subprocess.check_output([tcPath, "-s", "qdisc", "show", "dev", defaultDev])
    #split in to the qdiscs and then remove the empty place at [0].
    splitString = tcReturnVal.split("qdisc")
    splitString.pop(0)



    for x in splitString:
        #split into lines
        stringLine = x.split("\n")
        #there are three lines...
        nameLine = stringLine[0].split(" ")
        statsLine = stringLine[1].split(" ")
        rateLine = stringLine[2].split(" ")

        queueType = nameLine[1]
        queueName = nameLine[2].replace(':','-')
        rootOrParent = nameLine[3]

        nameArray.append({'name':queueName,'type':queueType,'rootOrParent':rootOrParent})

        fullFileName = (workingPath + queueName + ".rrd").replace(":","-")
        rrdtool.create(fullFileName,
            '--step', '5',
            'DS:packetSent:COUNTER:10:U:U',
            'DS:bytesSent:COUNTER:10:U:U',
            'DS:dropped:COUNTER:10:U:U',
            'DS:overlimits:COUNTER:10:U:U',
            'DS:requeues:COUNTER:10:U:U',
            'RRA:AVERAGE:0.5:1:600',
            'RRA:AVERAGE:0.5:6:360')


def graphRRD():
    global nameArray
    DEFString = list()
    LINEString = list()
    VDEFString = list()
    commentString = list()
    gprintString = list()
    graphColor = ['#000000', '#FF0000', '#00FF00', '#005555', '#FFFF00']
    graphType = ["packetSent", "bytesSent", "dropped", "overlimits", "requeues"]
    for dataType in graphType:
        if dataType == "bytesSent":
            units = '  B/s'
        else:
            units = 'pkt/s'
        for index,graph in enumerate(nameArray):
            fileName = (workingPath + graph['name'] + ".rrd").replace(":","-")
            DEFString.append('DEF:' + graph['name'] + '=' + fileName +
                ':' + dataType + ':AVERAGE')
            if graph['rootOrParent'] == 'root':
                LINEString.append('AREA:' + graph['name'] + graphColor[index] + ':'
                + graph['type'] + ' ' + graph['name'].replace('-','\:'))

            else:
                LINEString.append('LINE1:' + graph['name'] + graphColor[index] + ':'
                + graph['type'] + ' ' + graph['name'].replace('-','\:'))
            LINEString.append('GPRINT:' + graph['name'] + ':AVERAGE:Avg\:%5.2lf%S' + units)
            LINEString.append('GPRINT:' + graph['name'] + ':MAX:Max\:%5.2lf%S' + units)
            LINEString.append('GPRINT:' + graph['name'] + ':MIN:Min\:%5.2lf%S' + units)
            LINEString.append('GPRINT:' + graph['name'] + ':LAST:Cur\:%5.2lf%S' + units + '\t\t\t\t\t\t')

        graphFileName = (workingPath + dataType + ".png")
        initVars = [graphFileName, '--width', '800',
            '--height', '400',
            '--end', 'now', '--start', 'end-' + str(graphTimeWindowSec) + 's', '--title', dataType,
            '--vertical-label', units, '--slope-mode']
        initVars.extend(DEFString)
        initVars.extend(commentString)
        initVars.extend(LINEString)

        rrdtool.graph(*initVars)
        VDEFString = list()
        DEFString = list()
        LINEString = list()
        commentString = list()
        gprintString = list()

createRRD()
writeHtmlFiles()
while True:
    updateRRD()
    graphRRD()
    time.sleep(5)


