"""
Reads file metadata from database and transforms files into
index pages for each court, listing years and cases.
"""

from dateutil.parser import parse as dateparse
from lxml import etree
import os
import traceback

from StringIO import StringIO

import courts
from general import broadcast, \
    ConversionError, \
    Counter, \
    DatabaseManager, \
    ProcessManager, \
    StandardConversionError

# must use a global variable to ensure it is visible throughout the process pool
with open("template_index.html",'r') as html_template_file:
    html_template_index_stringio = StringIO(html_template_file.read())


months = ["", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"]

def make_indexes(dbfile_name, logfile, output_dir, use_multiprocessing):
    "Driver function - gathers courtlist and begins multiprocessing"

    print "-"*25
    print "Conversion..."

    finished_count = Counter()

    def convert_report(basename):
        "Callback function; reports on success or failure"
        def closure(report):
            "Take True and a list of report strings, or false and a message"
            (status, results) = report
            try:
                if status:
                    finished_count.inc()
                    if len(results)>0:
                        logfile.write("[convert success] "
                            + basename
                            + " ("
                            + ", ".join(results)
                            + ")" + "\n")
                    print "convert:%6d. %s" % (finished_count.count, basename)
                else:
                    raise StandardConversionError(results)
            except ConversionError, e:
                e.log("indexing fail", basename, logfile)

        return closure

    print "Generating indexes"
    with ProcessManager(use_multiprocessing, verbose=True) as process_pool:

        # Index by court ID
        with DatabaseManager(dbfile_name, use_multiprocessing) as cursor:
            courtlist = list(cursor.execute('SELECT courtid, name FROM courts'))

        process_pool.apply_async(
            make_top_index, (output_dir,), callback=convert_report("top"))

        for (court_id, name) in courtlist:
            process_pool.apply_async(make_court_index,
                (court_id, name, dbfile_name, use_multiprocessing, output_dir),
                callback=convert_report(name))

    broadcast(logfile,
        "Converted %d files successfully" % finished_count.count)

def make_element(tag, attribs, text):
    "Convenience wrapper around etree.Element"
    e = etree.Element(tag)
    for a in attribs:
        e.attrib[a] = attribs[a]
    e.text = text
    return e

def make_court_index(court_id, name, dbfile_name, \
    use_multiprocessing, output_dir):
    "Make index page for individual court"
    current_year = 0
    current_month = 0
    year_content_div = None
    try:

        # See notes in convert.py
        XHTML_NS = "{http://www.w3.org/1999/xhtml}"
        template = etree.parse(html_template_index_stringio)

        template.find('//{0}title'.format(XHTML_NS)).text \
            = name + ": Judgmental"

        template.find('//{0}div[@id="content"]/{0}h1'\
            .format(XHTML_NS)).text = name

        template.find('//{0}span[@id="bc-courtname"]'\
            .format(XHTML_NS)).text = name

        missing_index = template.find('//{0}div[@class="index"]'\
            .format(XHTML_NS))

        missing_index.text = ""
        table = make_element("table", {}, "")
        missing_index.append(table)


        short_name = \
            [shortname for (shortname, longname) in courts.courts \
                if longname == name][0]

        with DatabaseManager(dbfile_name, use_multiprocessing) as cursor:
            judgments = list(cursor.execute('''
                SELECT date
                    , judgmentid
                    , title
                    , judgmental_url
                FROM judgments
                WHERE courtid=:X
                    AND judgmental_url IS NOT NULL
                    ORDER BY date DESC
                ''', {"X": court_id}))
            print "%d judgments found" % len(judgments)

            for j in judgments:

                date, judgmentid, title, judgmental_url = j

                date = dateparse(date)
                if date.year != current_year or date.month != current_month:
                    # strftime doesn't work with dates before 1900
                    month_human = months[date.month] + " " + str(date.year)
                    month_id = "%d-%d" % (date.year, date.month)
                    print month_human
                    current_year = date.year
                    current_month = date.month

                    table_row = make_element("tr", {}, "")
                    table_header = make_element("td", {}, "")
                    table_content = make_element("td", {}, "")
                    table_row.append(table_header)
                    table_row.append(table_content)
                    table.append(table_row)

                    year_head_div = make_element("div",
                        {"class": "index-year",
                            "onclick": 'showHide("%s");' % month_id},
                        month_human + "\n")
                    table_header.append(year_head_div)

                    year_content_div = make_element("div",
                        {"class": "index-judgments",
                            "id": month_id, "style": "display: none"}, "")
                    table_content.append(year_content_div)

                case = make_element("div", {"class": "row"}, "")
                link = make_element("a", {"href": judgmental_url}, title)
                case.append(link)
                case.tail = "\n"
                year_content_div.append(case)

        outfile = open(os.path.join(
            output_dir, short_name+"/index.html"),'w')
        outfile.write(etree.tostring(template, pretty_print=True))

        return (True,"")


    except ConversionError, e:
        return (False, e.message)
    except Exception, e:
        # Something really unexpected happened
        return (False, traceback.format_exc())


def make_top_index(output_dir):
    "Make top index page - a little different from court indices"
    try:
        print "make_top_index"
        XHTML_NS = "{http://www.w3.org/1999/xhtml}" # See notes in convert.py
        template = etree.parse(html_template_index_stringio)
        name = "All Courts and Tribunals"

        template.find('//{0}title'.format(XHTML_NS)).text \
            = name + ": Judgmental"

        template.find('//{0}div[@id="content"]/{0}h1'\
            .format(XHTML_NS)).text = name

        template.find('//{0}span[@id="bc-courtname"]'\
            .format(XHTML_NS)).text = ""

        missing_index = template.find('//{0}div[@class="index"]'\
            .format(XHTML_NS))

        missing_index.text = ""

        for category in ["United Kingdom",
            "England and Wales",
            "Scotland",
            "Northern Ireland",
            "Republic of Ireland",
            "Europe"]:
            header = make_element("h2", {}, category)
            missing_index.append(header)

            for short in courts.categories[category]:
                longname = [ y for (x, y) in courts.courts if x == short] [0]
                case = make_element("div", {"class": "row"}, "")
                link = make_element("a", {"href": "/judgments/"+short+"/"},
                    longname)
                case.append(link)
                case.tail = "\n"
                missing_index.append(case)

        print "    writing to ../index_nonlive.html";

        outfile = open(os.path.join(output_dir,"../index_nonlive.html"),'w')
        outfile.write(etree.tostring(template, pretty_print=True))
        return (True,"")

    except ConversionError, e:
        return (False, e.message)
    except Exception, e:
        # Something really unexpected happened
        return (False, traceback.format_exc())

class CantFindElement(ConversionError):
    def __init__(self, searchstring):
        self.message = "can't find element '%s'" % searchstring

if __name__ == "__main__":
    make_indexes("../judgmental_nonlive.db", open("errors.log", "w"),
        "indexes", False)
