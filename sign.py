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
import logging

UI_FILE="/usr/share/digital-signage/sign.ui"
TEST_PATTERN="/usr/share/digital-signage/test-pattern.png"
CONFIG_FILE="/etc/sign/config.ini"
LOGGER_NAME="digital-signage"

logger = logging.getLogger(LOGGER_NAME)

class DigitalSignage:
    compass_directions = { 'N': range(338,359) + range(0, 22),
                           'NE': range(23,67),
                           'E': range(68,112),
                           'SE': range(113,158),
                           'S': range(159, 202),
                           'SW': range(203, 248),
                           'W': range(249, 297),
                           'NW': range(298, 337) }

    # U+2191 and U+2193 are the up and down arrows, respectively
    barometer_directions = { "0": "",
                             "1": u'\u2191',
                             "2": u'\u2193' }

    def __init__(self, options, config_dictionary):
        defaultScreen = Gdk.Screen.get_default()
        self.monitorGeometry = defaultScreen.get_monitor_geometry(defaultScreen.get_primary_monitor())
        self.screenSize = (self.monitorGeometry.x + self.monitorGeometry.width,
                           self.monitorGeometry.y + self.monitorGeometry.height)
        logger.debug("Actual screen size: %s", self.screenSize)
        handlers = {}
        self.config = { 'update_interval': '20',
                        'weather_uri': None,
                        'slide_directory': '/var/spool/digital-signage/slides',
                        'screen_size': '1024x768',
                        'logo': '',
                        }
        self.config.update(config_dictionary)
        logger.debug("Loaded configuration: %s", self.config)
        try:
            self.config["update_interval"] = int(self.config["update_interval"]) * 1000
        except ValueError:
            sys.exit("Invalid update interval: " + self.config["update_interval"])
        parse = re.match('^(\d+)x(\d+)$', self.config["screen_size"])
        if parse is None:
            sys.exit("Invalid screen size specified in config file")
        self.screenSize = (int(parse.group(1)), int(parse.group(2)))
        logger.debug("New screen size: %s", self.screenSize)
        # Load the UI and get objects we care about
        self.builder = Gtk.Builder()
        try: 
            self.builder.add_from_file(options.ui_file)
            logger.debug("UI Loaded")
        except GLib.GError, e:
            sys.exit("FATAL: Unable to load UI: " + e.message)
        self.winMain = self.builder.get_object("mainWindow")
        self.blackBackground = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, 
                                                    False, 8, 
                                                    self.screenSize[0], 
                                                    self.screenSize[1])
        self.img = self.builder.get_object("imgSign")
        self.img.set_from_pixbuf(self.blackBackground)
        self.black = Gdk.RGBA()
        self.black.parse("black")
        # unused?
        self.mitgrey = Gdk.RGBA()
        self.mitgrey.parse("#666666")
        self.mitred = Gdk.RGBA()
        self.mitred.parse("#993333")
        # Otherwise you get a 1px grey outline in some WMs
        self.winMain.override_background_color(0, self.black)
        self.winMain.set_position(Gtk.WindowPosition.CENTER)
        self.winMain.show()
        self.timeLabel = self.builder.get_object("lblTime")
        self.timeFormat = "%A\n\n%B %e, %Y\n\n%l:%M:%S %p"
        self.last_weather_update = 0
        self.notebook = self.builder.get_object("notebook1")
        white=Gdk.RGBA()
        white.parse("white")
        for obj in ("lblTime", "lblWeather", "lblWind", "lblVisibility", "lblHumidity", "lblPressure", "lblSunrise", "lblSunset"):
                self.builder.get_object(obj).override_color(0, white)
        self.prepare_slideshow()

    def tick(self):
        # Update the clock
        self.timeLabel.set_text(time.strftime(self.timeFormat, time.localtime(time.time())))
        return True

    def next_slide(self):
        if self.slide >= len(self.imgFiles):
            logger.debug("Ending slideshow...")
            self.clock_and_weather()
            return False
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(self.imgFiles[self.slide])
            logger.debug("Created pixbuf from %s", self.imgFiles[self.slide])
        except GLib.GError as e:
            logger.error("Pixbuf.new_from_file: %s", e.message)
            # Just move on to the next image
            self.slide += 1
            return True
        (width, height) = (pixbuf.get_width(), pixbuf.get_height())
        logger.debug("Original pixbuf dimensions: W:%d H:%d", width, height)
        scale_x = 1.0
        scale_y = 1.0
        # We used to just call GdkPixbuf.scale_simple(screenSize[0] if
        # screenSize[0] < width else width, etc), but composite can do
        # it for us
        if width > self.screenSize[0]:
            scale_x = float(self.screenSize[0]) / float(width)
            width = scale_x * float(width)
            logger.debug("Resizing width: scale_x=%f, width=%f", scale_x, width)
        if height > self.screenSize[1]:
            scale_y = float(self.screenSize[1]) / float(height)
            height = scale_y * float(height)
            logger.debug("Resizing height: scale_y=%f, height=%f", 
                         scale_y, height)
        dest_x = int((float(self.screenSize[0]) - width) / 2)
        dest_y = int((float(self.screenSize[1]) - height) / 2)
        width = int(width)
        height = int(height)
        # the above are ints, and everything else is floats according to Gdk
        # gi will cast the floats to ints where necessary, but might as well
        # be explicit
        offset_x = dest_x
        offset_y = dest_y
        destpixbuf = self.blackBackground.copy()
        logger.debug("Will composite pixbuf as follows: dest_x=%d, dest_y=%d, offset_x=%d, offset_y=%d, scale_x=%f, scale_y=%f, width=%f, height=%f", dest_x, dest_y, offset_x, offset_y, scale_x, scale_y, width, height)
        pixbuf.composite(destpixbuf, dest_x, dest_y, 
                         width, height,
                         offset_x, offset_y,
                         scale_x, scale_y, GdkPixbuf.InterpType.BILINEAR, 255)
        self.img.set_from_pixbuf(destpixbuf)
        self.slide += 1
        return True

    def prepare_slideshow(self):
        self.winMain.override_background_color(0, self.black)
        slide_directory = self.config["slide_directory"]
        self.imgFiles = []
        try:
            self.imgFiles = [ os.path.join(slide_directory, f) for f in os.listdir(slide_directory) if os.path.isfile(os.path.join(slide_directory, f)) ]
        except OSError as e:
            logger.error("Error while reading slide directory: %s ", e.message)
        if len(self.imgFiles) < 1:
            logger.debug("No images found")
            if os.path.exists(self.config["logo"]):
                self.imgFiles.append(self.config["logo"])
                logger.debug("Using logo: %s", 
                             self.config["logo"])
            else:
                logger.debug("No logo found, using test pattern")
                self.imgFiles.append(TEST_PATTERN)
        self.slide = 0
        # todo: determine what page the widget is on
        # rather than picking notebook pages by integer
        self.notebook.set_current_page(1)
        # render the window and set its size
        # possibly no longer needed with the black background?
        while Gtk.events_pending():
            Gtk.main_iteration()
        GObject.timeout_add(self.config["update_interval"], self.next_slide)
        self.next_slide()
        return False
    
    def clock_and_weather(self):
        self.update_forecast()
        # TODO: why do we do this here?
        self.img.set_from_pixbuf(self.blackBackground)
        self.winMain.override_background_color(0, self.mitred)
        self.notebook.set_current_page(0)
        GObject.timeout_add(self.config["update_interval"], self.prepare_slideshow)

    def update_forecast(self):
        if self.last_weather_update > time.time():
            return
        feed = feedparser.parse(self.config["weather_uri"])
        if len(feed.entries) == 0 or feed.status != 200:
            logger.warn("Could not retrieve weather: Status %d, %s", feed.status if hasattr(feed, 'status') else 0, feed.bozo_exception)
            self.builder.get_object("lblWeather").set_text("(weather unavailable)")
            for obj in ("lblWind", "lblVisibility", "lblHumidity", "lblPressure", "lblSunrise", "lblSunset"):
                self.builder.get_object(obj).set_text("")
            return
        self.last_weather_update = time.time() + 300
        conditions = feed.entries[0].yweather_condition
        units = feed.feed.yweather_units
        atmo = feed.feed.yweather_atmosphere
        wind = feed.feed.yweather_wind
        astro = feed.feed.yweather_astronomy
        windtxt = "n/a"
        try:
            for i in self.compass_directions:
                if int(wind["direction"]) in self.compass_directions[i]:
                    windtxt = "%s %s%s" % (i, wind["speed"], units["speed"])
                    break
        except ValueError:
            logger.debug("Couldn't parse wind direction: %s", wind["direction"])
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
    logging.basicConfig(level=logging.WARN)
    if options.debug:
        logger.setLevel(logging.DEBUG)
    config = ConfigParser.RawConfigParser()
    config.readfp(io.BytesIO("[Sign]\n"))
    config.read(options.config_file)
    Gtk.init(None);
    sign = DigitalSignage(options, dict(config.items('Sign')))
    main_loop = GObject.MainLoop ()
    GObject.timeout_add(100, sign.tick)
    main_loop.run ()
