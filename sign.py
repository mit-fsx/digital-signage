#!/usr/bin/python

from gi.repository import GObject
from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf

import sys
import time
import os
import feedparser
from optparse import OptionParser

UI_FILE="/usr/share/digital-signage/signage.ui"
SLIDES="/home/jdreed/src/signage/python/slides"
#SLIDES="/usr/share/digital-signage"

class DigitalSignage:

    def __init__(self, options):
        self.debugMode = options.debug
        handlers = {}

        defaultScreen = Gdk.Screen.get_default()
        self.monitorGeometry = defaultScreen.get_monitor_geometry(defaultScreen.get_primary_monitor())
        self.screenSize = (self.monitorGeometry.x + self.monitorGeometry.width,
                           self.monitorGeometry.y + self.monitorGeometry.height)
        self.screenSize = (1024, 768)

        # Load the UI and get objects we care about
        self.builder = Gtk.Builder()
        try: 
            self.builder.add_from_file(options.ui_file)
        except GLib.GError, e:
            print >> sys.stderr, "FATAL: Unable to load UI: ", e
            sys.exit(-1)

        self.winMain = self.builder.get_object("mainWindow")
        self.winMain.set_position(Gtk.WindowPosition.CENTER)
        self.winMain.show()
        self.timeLabel = self.builder.get_object("lblTime")
        self.timeFormat = "%A\n\n%B %e, %Y\n\n%l:%M:%S %p"
        self.notebook = self.builder.get_object("notebook1")
        self.img = self.builder.get_object("imgSign")
#        self.clock_and_weather()
        self.slideshow()

    def _debug(self, *args):
        if self.debugMode:
            if type(args[0]) is str and len(args) > 1:
                print >> sys.stderr, "D: " + args[0], args[1:]
            else:
                print >> sys.stderr, "D: ", args[0]

    # General purpose time callback
    def tick(self):
        self.timeLabel.set_text(time.strftime(self.timeFormat, time.localtime(time.time())))
        print >>sys.stderr, "tick"
        return True

    def next_slide(self):
        print >>sys.stderr, "next slide", self.slide, len(self.imgFiles)
        if self.slide >= len(self.imgFiles):
            print >>sys.stderr, "end show"
            self.clock_and_weather()
            return False
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(os.path.join(SLIDES, self.imgFiles[self.slide]))
#            scaled = pixbuf.scale_simple(self.screenSize[0], self.screenSize[1], GdkPixbuf.InterpType.BILINEAR)
        except GLib.GError, e:
            # Just move on to the next image
            self.slide += 1
            return True
#            print >>sys.stderr, "Error", e
        self.slide += 1
        self.img.set_from_pixbuf(pixbuf)
        return True

    def slideshow(self):
        # todo: determine what page the widget is on
        try:
            self.imgFiles = [ f for f in os.listdir(SLIDES) if os.path.isfile(os.path.join(SLIDES, f)) ]
        except OSError:
            print >>sys.stderr, "slides missing"
        self.slide = 0
        GObject.timeout_add(1000, self.next_slide)
        self.blackBackground = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, self.screenSize[0], self.screenSize[1])
        self.img.set_from_pixbuf(self.blackBackground)
        self.notebook.set_current_page(1)
        # render the window and set its size
        while Gtk.events_pending():
            Gtk.main_iteration()
        self.next_slide()

    
    def clock_and_weather(self):
        self.update_forecast()
        self.notebook.set_current_page(0)

        

    def update_forecast(self):
        URL="http://weather.yahooapis.com/forecastrss?w=2373572&u=f"
        feed = feedparser.parse(URL)
        print >>sys.stderr, feed
        if feed.status != 200:
            pass
        print >>sys.stderr, "error getting forecast"
        conditions = feed.entries[0].yweather_condition
        units = feed.feed.yweather_units
        atmo = feed.feed.yweather_atmosphere
#        str = "Weather as of %s\n%s %s%s" % (conditions["date"], conditions["text"], conditions["temp"], units["temperature"])
        # U+00B0 is the degree sign
        str = "%s%s%s, %s" % (conditions["temp"], u'\u00b0', units["temperature"], conditions["text"])
        self.builder.get_object("lblWeather").set_text(str)

                  
if __name__ == '__main__':
    parser = OptionParser()
    parser.set_defaults(debug=False)
    parser.add_option("--debug", action="store_true", dest="debug")
    parser.add_option("--ui", action="store", type="string",
                      default=UI_FILE, dest="ui_file")
    (options, args) = parser.parse_args()
    Gtk.init(None);
    main_loop = GObject.MainLoop ()
    sign = DigitalSignage(options)
    GObject.timeout_add(100, sign.tick)
    main_loop.run ()
