"""
Author: Chris Swan
Date:   5 Oct 2010
Updated with suggestions from Tim Swan: 6 Oct 2010

with thanks to Matt Weber (http://www.mattweber.org/2007/03/04/python-script-renamepy/)

Increment or decrement file names
"""

import os
import sys
from optparse import OptionParser

def ProcessFiles(options):

    # Set the offset to increment or decrement
    if options.inc:
        offset=options.offset
    else:
        offset=0-options.offset
        
    # Get directory to work on
    if options.directory:
        path = options.directory[0]
    else:
        path = os.getcwd()
    
    # Create a list of files in the directory
    fileList = os.listdir(path)
    
    # Reverse the list so that we don't get file name collisions
    if offset > 0:
        fileList.reverse()
        
    # Iterate across the list of files
    for file in fileList:
        
        # Get filename and the extension
        name, ext = os.path.splitext(file)
        oldname = os.path.join( path, name+ext )
        
        # Replace - first step
        if options.replace:
            for vals in options.replace:
                name = name.replace(vals[0], "*")
                replace = vals[1]
        
        # Extract digits from filename
        ndigits = ''.join([letter for letter in name if letter.isdigit()])
        # and the residual letters
        nletters = ''.join([letter for letter in name if not letter.isdigit()])

        # Process the inc/dec
        if ndigits != '':
            #Decrement the digits
            newdigits = str(int(ndigits)+offset)
            # and replace any zeros that may have been stripped by the int operation
            zeropad=len(ndigits)-len(newdigits)
            while zeropad>0:
                newdigits = "0"+newdigits
                zeropad=zeropad-1
        else:
            newdigits=""

        # Replace - second step
        if options.replace:
            nletters = nletters.replace("*", replace)
                
        # Create the new name
        newname = os.path.join( path , nletters + newdigits + ext )
        try:
            # Check for verbose output
            if options.verbose:
                print(oldname + " -> " + newname)
            # Rename the file
            os.rename(oldname, newname)
        except (OSError):
            print >>sys.stderr, ("Error renaming "+file+" to "+newname)
        

if __name__ == "__main__":
    """
    Parses command line and renames the files passed in
    """
    # Create the options we want to parse
    usage = "usage: %prog [options]"
    optParser = OptionParser(usage=usage)
    optParser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False, help="Use verbose output")
    optParser.add_option("-i", "--inc", action="store_true", dest="inc", default=False, help="Increment")
    optParser.add_option("-o", "--offset", type="int", dest="offset", default="1", help="Offset number")
    optParser.add_option("-d", "--dir", action="append", type="string", nargs=1, dest="directory", help="Directory to work on if not PWD")
    optParser.add_option("-r", "--replace", action="append", type="string", nargs=2, dest="replace", help="Replaces OLDVAL with NEWVAL in the filename", metavar="OLDVAL NEWVAL")
    (options, args) = optParser.parse_args()

    # Process files
    ProcessFiles(options)
 
    # exit successful
    sys.exit(0)
