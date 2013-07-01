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
import re
from optparse import OptionParser
import io
import ConfigParser

UI_FILE="/usr/share/digital-signage/sign.ui"
CONFIG_FILE="/etc/sign/config.ini"

class DigitalSignage:
    compass_directions = { 'N': range(338,359) + range(0, 22),
                           'NE': range(23,67),
                           'E': range(68,112),
                           'SE': range(113,158),
                           'S': range(159, 202),
                           'SW': range(203, 248),
                           'W': range(249, 297),
                           'NW': range(298, 337) }
    barometer_directions = { "0": "",
                             "1": u'\u2191',
                             "2": u'\u2193' }

    def __init__(self, options, config_dictionary):
        self.debugMode = options.debug
        defaultScreen = Gdk.Screen.get_default()
        self.monitorGeometry = defaultScreen.get_monitor_geometry(defaultScreen.get_primary_monitor())
        self.screenSize = (self.monitorGeometry.x + self.monitorGeometry.width,
                           self.monitorGeometry.y + self.monitorGeometry.height)
        handlers = {}
        self.config = { 'update_interval': '60',
                        'weather_uri': None,
                        'slide_directory': '/var/spool/digital-signage/slides',
                        'screen_size': '1024x768',
                        }
        self.config.update(config_dictionary)
        try:
            self.config["update_interval"] = int(self.config["update_interval"])
        except ValueError:
            print >>sys.stderr, "Invalid update interval: " + self.config["update_interval"]
            sys.exit(0)
        parse = re.match('^(\d+)x(\d+)$', self.config["screen_size"])
        if parse is None:
            print >>sys.stderr, "Invalid screen size"
        self.screenSize = (int(parse.group(1)), int(parse.group(2)))

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
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(os.path.join(self.config["slide_directory"], self.imgFiles[self.slide]))
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
        slide_directory = self.config["slide_directory"]
        self.imgFiles = []
        try:
            self.imgFiles = [ f for f in os.listdir(slide_directory) if os.path.isfile(os.path.join(slide_directory, f)) ]
        except OSError:
            print >>sys.stderr, "slides missing"
        if len(self.imgFiles) < 1:
            self.imgFiles.append(self.config["logo"])
        self.slide = 0
        self.blackBackground = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, self.screenSize[0], self.screenSize[1])
        self.img.set_from_pixbuf(self.blackBackground)
        self.notebook.set_current_page(1)
        # render the window and set its size
        while Gtk.events_pending():
            Gtk.main_iteration()
        GObject.timeout_add(1000, self.next_slide)
        self.next_slide()

    
    def clock_and_weather(self):
        self.update_forecast()
        self.notebook.set_current_page(0)

    def update_forecast(self):
        feed = feedparser.parse(self.config["weather_uri"])
        if len(feed.entries) == 0 or feed.status != 200:
            print >>sys.stderr, "error getting forecast"
        else:
            conditions = feed.entries[0].yweather_condition
            units = feed.feed.yweather_units
            atmo = feed.feed.yweather_atmosphere
            wind = feed.feed.yweather_wind
            astro = feed.feed.yweather_astronomy
            print >>sys.stderr, astro, atmo
            windtxt = "n/a"
            try:
                for i in self.compass_directions:
                    if int(wind["direction"]) in self.compass_directions[i]:
                        windtxt = "%s %s%s" % (i, wind["speed"], units["speed"])
                        break
            except ValueError:
                pass
            # U+00B0 is the degree sign
            str = "%s%s%s, %s" % (conditions["temp"], u'\u00b0', units["temperature"], conditions["text"])
            self.builder.get_object("lblWeather").set_text(str)
            self.builder.get_object("lblWind").set_text("Wind: " + windtxt)
            self.builder.get_object("lblVisibility").set_text("Visibility: " + atmo["visibility"] + units["distance"])
            self.builder.get_object("lblHumidity").set_text("Humidity: %s%%" % atmo["humidity"])
            self.builder.get_object("lblPressure").set_text("Pressure: %s%s %s" % (atmo["pressure"], units["pressure"], self.barometer_directions[atmo["rising"]]))
            self.builder.get_object("lblSunrise").set_text("Sunrise: " + astro["sunrise"])
            self.builder.get_object("lblSunset").set_text("Sunset: " + astro["sunset"])
                  
if __name__ == '__main__':
    parser = OptionParser()
    parser.set_defaults(debug=False)
    parser.add_option("--debug", action="store_true", dest="debug")
    parser.add_option("--ui", action="store", type="string",
                      default=UI_FILE, dest="ui_file")
    parser.add_option("--cfg", action="store", type="string",
                      default=CONFIG_FILE, dest="config_file") 
    (options, args) = parser.parse_args()
    config = ConfigParser.RawConfigParser()
    config.readfp(io.BytesIO("[Sign]\n"))
    config.read(options.config_file)
    Gtk.init(None);
    sign = DigitalSignage(options, dict(config.items('Sign')))
    main_loop = GObject.MainLoop ()
    GObject.timeout_add(100, sign.tick)
    main_loop.run ()
