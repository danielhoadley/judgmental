"""
An object representing a judgment and its metadata, and some standard errors in producing them.
"""

from lxml import html
import os


class Judgment():
    "Represents a single judgment"

    def __init__(self,html,infilename):
        self.html = html
        self.infilename = infilename
        self.outbasename = os.path.basename(infilename)

    def write_html(self,f):
        f.write(html.tostring(self.html, pretty_print = True))

    def write_html_to_dir(self,dirname):
        o = open(os.path.join(dirname,self.outbasename), 'w')
        self.write_html(o)
        o.close()



class ConversionError(Exception):
    def log(self,f,logfile):
        logfile.write("%s: %s"%(f,self.message))


class StandardConversionError(ConversionError):
    def __init__(self,message):
        self.message = message


class Duplicate(ConversionError):
    def __init__(self,old):
        self.message = "duplicate of %s"%old