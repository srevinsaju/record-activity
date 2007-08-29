#Copyright (c) 2007, Media Modifications Ltd.

#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:

#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.

#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.


import urllib
import string
import fnmatch
import os
import random
import cairo
import gtk
import pygtk
pygtk.require('2.0')
import shutil

import math
import gtk.gdk
import sugar.env
import random
import time
from time import strftime
import gobject
import xml.dom.minidom
from xml.dom.minidom import getDOMImplementation
from xml.dom.minidom import parse
from hashlib import md5

from recorded import Recorded
from color import Color

from sugar import util
from sugar.datastore import datastore

import _camera


class Model:
	def __init__( self, pca ):
		#todo: this might all need to be relocated b/c of datastore
		self.ca = pca
		self.setConstants()

		self.mediaHashs = {}
		self.mediaHashs[self.TYPE_PHOTO] = []
		self.mediaHashs[self.TYPE_VIDEO] = []
		self.mediaHashs[self.TYPE_AUDIO] = []


	def fillMediaHash( self, index ):
		print("fillMediaHash 1")
		if (os.path.exists(index)):
			print("fillMediaHash 2")
			doc = parse( os.path.abspath(index) )

			photos = doc.documentElement.getElementsByTagName('photo')
			for each in photos:
				self.loadMedia( each, self.mediaHashs[self.TYPE_PHOTO] )

			videos = doc.documentElement.getElementsByTagName('video')
			for each in videos:
				self.loadMedia( each, self.mediaHashs[self.TYPE_VIDEO] )

			audios = doc.documentElement.getElementsByTagName('audio')
			for each in audios:
				self.loadMedia( each, self.mediaHashs[self.TYPE_AUDIO] )


	def loadMedia( self, el, hash ):
		recd = Recorded( self.ca )
		addToHash = True

		recd.type = int(el.getAttribute('type'))
		recd.title = el.getAttribute('title')
		recd.time = int(el.getAttribute('time'))
		recd.photographer = el.getAttribute('photographer')
		recd.mediaFilename = el.getAttribute('mediaFilename')
		recd.thumbFilename = el.getAttribute('thumbFilename')

		colorStrokeHex = el.getAttribute('colorStroke')
		colorStroke = Color()
		colorStroke.init_hex( colorStrokeHex )
		recd.colorStroke = colorStroke
		colorFillHex = el.getAttribute('colorFill')
		colorFill = Color()
		colorFill.init_hex( colorFillHex )
		recd.colorFill = colorFill

		recd.buddy = (el.getAttribute('buddy') == "True")
		recd.hashKey = el.getAttribute('hashKey')
		recd.mediaMd5 = el.getAttribute('mediaMd5')
		recd.thumbMd5 = el.getAttribute('thumbMd5')

		recd.datastoreNode = el.getAttributeNode("datastoreId")
		#recd.datastoreId = el.getAttribute('datastoreId')
		if (recd.datastoreNode != None):
			recd.datastoreId = recd.datastoreNode.nodeValue
			#quickly check, if you have a datastoreId, that the file hasn't been deleted, thus we need to flag your removal
			#todo: find better method here (e.g., datastore.exists(id))
			self.loadMediaFromDatastore( recd )
			if (recd.datastoreOb == None):
				print("~~> recd.datastoreId", recd.datastoreId )
				addToHash = False
			else:
				#name might have been changed in the journal, so reflect that here
				recd.title = recd.datastoreOb.metadata['title']
			recd.datastoreOb == None

		#buddyThumbString = el.getAttribute('buddyThumb')
		#print("buddyThumbString...", buddyThumbString )
		bt = el.getAttributeNode('buddyThumb')
		if (not bt == None):
			#todo: consolidate this code into a function...
			pbl = gtk.gdk.PixbufLoader()
			import base64
			data = base64.b64decode( bt.nodeValue )
			pbl.write(data)
			thumbImg = pbl.get_pixbuf()
			#todo: add check for what to do if there is no thumbFilename!
			thumbPath = os.path.join(self.ca.journalPath, recd.thumbFilename)
			thumbImg.save(thumbPath, "jpeg", {"quality":"85"} )

		if (addToHash):
			hash.append( recd )


	def selectLatestThumbs( self, type ):
		p_mx = len(self.mediaHashs[type])
		p_mn = max(p_mx-self.ca.ui.numThumbs, 0)
		#gobject.idle_add(self.setupThumbs, type, p_mn, p_mx)
		self.setupThumbs( type, p_mn, p_mx )


	def isVideoMode( self ):
		return self.MODE == self.MODE_VIDEO


	def isPhotoMode( self ):
		return self.MODE == self.MODE_PHOTO


	def setupThumbs( self, type, mn, mx ):
		if (not type == self.MODE):
			return

		self.setUpdating( True )

		hash = self.mediaHashs[type]

		#don't load more than you possibly need by accident
		if (mx>mn+self.ca.ui.numThumbs):
			mx = mn+self.ca.ui.numThumbs
		mx = min( mx, len(hash) )

		if (mn<0):
			mn = 0

		if (mx == mn):
			mn = mx-self.ca.ui.numThumbs

		if (mn<0):
			mn = 0

		#
		#	UI
		#
		#at which # do the left and right buttons begin?
		left = -1
		rigt = -1
		if (mn>0):
			left = max(0, mn-self.ca.ui.numThumbs)
		rigt = mx
		if (mx>=len(hash)):
			rigt = -1

		#get these from the hash to send over
		addToTray = []
		for i in range (mn, mx):
			addToTray.append( hash[i] )

		self.ca.ui.updateThumbs( addToTray, left, mn, rigt  )
		self.setUpdating( False )


	def getHash( self ):
		type = -1
		if (self.MODE == self.MODE_PHOTO):
			type = self.TYPE_PHOTO
		if (self.MODE == self.MODE_VIDEO):
			type = self.TYPE_VIDEO
		if (self.MODE == self.MODE_AUDIO):
			type = self.TYPE_AUDIO

		if (type != -1):
			return self.mediaHashs[type]
		else:
			return None


	def doShutter( self ):
		if (self.UPDATING):
			return

		if (self.MODE == self.MODE_PHOTO):
			self.startTakingPhoto()
		elif (self.MODE == self.MODE_VIDEO):
			if (not self.RECORDING):
				self.startRecordingVideo()
			else:
				self.stopRecordingVideo()
		elif (self.MODE == self.MODE_AUDIO):
			if (not self.RECORDING):
				self.startRecordingAudio()
			else:
				self.stopRecordingAudio()


	def startRecordingAudio( self ):
		print("start recording audio")
		self.setUpdating( True )
		self.setRecording( True )
		self.ca.glive.startRecordingAudio( )
		self.setUpdating( False )


	def stopRecordingAudio( self ):
		self.setUpdating( True )
		self.ca.glive.stopRecordingAudio( )
		self.setRecording( False )
		self.ca.glive.stop


	def saveAudio( self, tempPath, pixbuf ):
		print("stop recording audio")
		self.setUpdating( True )
		#todo: necc?
		self.ca.ui.hideLiveWindows()
		self.ca.ui.hidePlayWindows()

		recd = self.createNewRecorded( self.TYPE_AUDIO )
		oggPath = os.path.join(self.ca.journalPath, recd.mediaFilename)
		thumbPath = os.path.join(self.ca.journalPath, recd.thumbFilename)
		thumbImg = self.generateThumbnail(pixbuf, float(0.1671875))

		#todo: need to save the fullpixbuf to the xml only for display (for now, thumbnail)

		#todo: unneccassary to move to oggpath? or temp should *be* oggpath
		shutil.move(tempPath, oggPath)

		#at this point, we have both audio and thumb path, so we can save the recd
		self.createNewRecordedMd5Sums( recd )

		audioHash = self.mediaHashs[self.TYPE_AUDIO]
		audioHash.append( recd )
		self.thumbAdded( self.TYPE_AUDIO )

		self.doPostSaveVideo()


	def startRecordingVideo( self ):
		print("start recording video")
		self.setUpdating( True )
		self.setRecording( True )

		self.ca.ui.recordVideo()

		self.setUpdating( False )


	def setUpdating( self, upd ):
		self.UPDATING = upd
		self.ca.ui.updateButtonSensitivities()


	def setRecording( self, rec ):
		self.RECORDING = rec
		self.ca.ui.updateButtonSensitivities()


	def stopRecordingVideo( self ):
		print("stop recording video")
		self.setUpdating( True )

		self.ca.ui.hideLiveWindows()
		self.ca.ui.hidePlayWindows()

		self.ca.glive.stopRecordingVideo()


	def saveVideo( self, pixbuf, tempPath ):
		recd = self.createNewRecorded( self.TYPE_VIDEO )

		oggPath = os.path.join(self.ca.journalPath, recd.mediaFilename)
		thumbPath = os.path.join(self.ca.journalPath, recd.thumbFilename)

		#todo: dynamic creation of this ratio
		thumbImg = self.generateThumbnail(pixbuf, float(.66875) )
		thumbImg.write_to_png(thumbPath)
		#thumb = pixbuf.scale_simple( self._thuPho.tw, self._thuPho.th, gtk.gdk.INTERP_BILINEAR )
		#thumb.save( thumbpath, "jpeg", {"quality":"85"} )

		#todo: unneccassary to move to oggpath? or temp should *be* oggpath
		shutil.move(tempPath, oggPath)

		#at this point, we have both video and thumb path, so we can save the recd
		self.createNewRecordedMd5Sums( recd )

		videoHash = self.mediaHashs[self.TYPE_VIDEO]
		videoHash.append( recd )
		self.thumbAdded( self.TYPE_VIDEO )

		self.doPostSaveVideo()


	def cannotSaveVideo( self ):
		print("bad recorded video")
		self.doPostSaveVideo()


	def doPostSaveVideo( self ):
		#resume live video from the camera (if the activity is active)
		if (self.ca.ACTIVE):
			self.ca.ui.updateVideoComponents()
			self.ca.glive.play()

		self.setRecording( False )
		self.setUpdating( False )


	def stoppedRecordingVideo( self ):
		print("stoppedRecordingVideo")
		self.setUpdating( False )


	def startTakingPhoto( self ):
		self.setUpdating( True )
		self.ca.glive.takePhoto()


	def savePhoto( self, pixbuf ):
		recd = self.createNewRecorded( self.TYPE_PHOTO )

		imgpath = os.path.join(self.ca.journalPath, recd.mediaFilename)
		pixbuf.save( imgpath, "jpeg" )

		thumbpath = os.path.join(self.ca.journalPath, recd.thumbFilename)
		#todo: generate this dynamically
		thumbImg = self.generateThumbnail(pixbuf, float(0.1671875))
		thumbImg.write_to_png(thumbpath)
		#todo: use this code...?
		#thumb = pixbuf.scale_simple( self._thuPho.tw, self._thuPho.th, gtk.gdk.INTERP_BILINEAR )
		#thumb.save( thumbpath, "jpeg", {"quality":"85"} )

		#now that we've saved both the image and its pixbuf, we get their md5s
		self.createNewRecordedMd5Sums( recd )
		self.addPhoto( recd )

		#hey, i just took a cool picture!  let me show you!
		if (self.ca.meshClient != None):
			#todo: md5?
			self.ca.meshClient.notifyBudsOfNewPhoto( recd )



	def _get_base64_pixbuf_data(self, pixbuf):
		data = [""]
		pixbuf.save_to_callback(self._save_data_to_buffer_cb, "png", {}, data)

		import base64
		return base64.b64encode(str(data[0]))


	def _save_data_to_buffer_cb(self, buf, data):
		data[0] += buf
		return True


	def removeMediaFromDatastore( self, recd ):
		print("removeMediaFromDatastore 1")
		#before this method is called, the media are removed from the file
		if (recd.datastoreId == None):
			return

		try:
			recd.datastoreOb.destroy()
			print("removeMediaFromDatastore 2")
			datastore.delete( recd.datastoreId )

			del recd.datastoreId
			recd.datastoreId = None

			del recd.datastoreOb
			recd.datastoreOb = None

			print("removeMediaFromDatastore 3")
		finally:
			#todo: add error message here
			print("removeMediaFromDatastore 4")
			pass


	def loadMediaFromDatastore( self, recd ):
		#todo: make sure methods calling this handle None as a response

		if (recd.datastoreId == None):
			print("RecordActivity error -- request for recd from datastore with no datastoreId")
			return None

		mediaObject = None
		try:
			mediaObject = datastore.get( recd.datastoreId )
		finally:
			if (mediaObject == None):
					print("RecordActivity error -- request for recd from datastore returning None")
					return None

		recd.datastoreOb = mediaObject


	def addPhoto( self, recd ):
		#todo: sort on time-taken, not on their arrival time over the mesh (?)
		self.mediaHashs[self.TYPE_PHOTO].append( recd )

		#updateUi
		self.thumbAdded(self.TYPE_PHOTO)

		self.setUpdating( False )


	#assign a better name here (name_0.jpg)
	def createNewRecorded( self, type ):
		recd = Recorded( self.ca )
		recd.hashKey = self.ca.hashedKey

		#to create a file, use the hardware_id+time *and* check if available or not
		nowtime = int(time.time())
		recd.time = nowtime

		mediaThumbFilename = str(recd.hashKey) + "_" + str(recd.time)
		mediaFilename = mediaThumbFilename

		recd.type = type
		titleStarter = ""
		if (type == self.TYPE_PHOTO):
			mediaFilename = mediaFilename + ".jpg"
			titleStarter = "Photo"
		if (type == self.TYPE_VIDEO):
			mediaFilename = mediaFilename + ".ogv"
			titleStarter = "Video"
		if (type == self.TYPE_AUDIO):
			mediaFilename = mediaFilename + ".ogg"
			titleStarter = "Audio"
		mediaFilename = self.getUniqueFilepath( mediaFilename, 0 )
		recd.mediaFilename = mediaFilename

		thumbFilename = mediaThumbFilename + "_thumb.jpg"
		thumbFilename = self.getUniqueFilepath( thumbFilename, 0 )
		recd.thumbFilename = thumbFilename

		recd.photographer = self.ca.nickName
		recd.title = titleStarter + " by " + str(recd.photographer)

		recd.colorStroke = self.ca.ui.colorStroke
		recd.colorFill = self.ca.ui.colorFill

		return recd


	def getUniqueFilepath( self, path, i ):
		pathOb = os.path.abspath( path )
		if (os.path.exists(pathOb)):
			i = i+1
			newPath = os.path.join( os.path.dirname(pathOb), str( str(i) + os.path.basename(pathOb) ) )
			path = getUniqueFilepath( str(newPath), i )
		else:
			return path


	def createNewRecordedMd5Sums( self, recd ):
		#load the thumbfile
		thumbFile = os.path.join(self.ca.journalPath, recd.thumbFilename)
		print( thumbFile, os.path.exists(thumbFile))
		thumbMd5 = self.md5File( thumbFile )
		recd.thumbMd5 = thumbMd5

		#load the mediafile
		mediaFile = os.path.join(self.ca.journalPath, recd.mediaFilename)
		mediaMd5 = self.md5File( mediaFile )
		recd.mediaMd5 = mediaMd5


	def md5File( self, filepath ):
		md = md5()
		f = file( filepath, 'rb' )
		md.update( f.read() )
		digest = md.hexdigest()
		hash = util.printable_hash(digest)
		return hash


	#outdated?
	def generateThumbnail( self, pixbuf, scale ):
#		#need to generate thumbnail version here
		thumbImg = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.ca.ui.tw, self.ca.ui.th)
		tctx = cairo.Context(thumbImg)
		img = _camera.cairo_surface_from_gdk_pixbuf(pixbuf)

		tctx.scale(scale, scale)
		tctx.set_source_surface(img, 0, 0)
		tctx.paint()
		return thumbImg


	def generateEmptyThumbnail( self ):
		thumbImg = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.ca.ui.tw, self.ca.ui.th)
		tctx = cairo.Context(thumbImg)
		tctx.set_source_rgb( 0, 1, 1 )
		tctx.rectangle(0, 0, self.ca.ui.tw, self.ca.ui.th)
		tctx.fill()
		tctx.paint()

		return thumbImg


	def deleteRecorded( self, recd, mn ):
		print("deleteRecorded 1")

		#remove files from the filesystem if not on the datastore
		if (recd.datastoreId == None):
			print("deleteRecorded 2")
			mediaFile = os.path.join(self.ca.journalPath, recd.mediaFilename)
			if (os.path.exists(mediaFile)):
				os.remove(mediaFile)

			thumbFile = os.path.join(self.ca.journalPath, recd.thumbFilename)
			if (os.path.exists(thumbFile)):
				os.remove(thumbFile)
		else:
			print("deleteRecorded 3")
			#remove from the datastore here, since once gone, it is gone...
			self.removeMediaFromDatastore( recd )

		#clear the index
		hash = self.mediaHashs[recd.type]
		index = hash.index(recd)
		hash.remove( recd )

		#update your own ui
		self.setupThumbs(recd.type, mn, mn+self.ca.ui.numThumbs)
		print("deleteRecorded 4")




	#todo: if you are not at the end of the list, do we want to force you to the end?
	def thumbAdded( self, type ):
		mx = len(self.mediaHashs[type])
		mn = max(mx-self.ca.ui.numThumbs, 0)
		self.setupThumbs(type, mn, mx)


	def doVideoMode( self ):
		if (self.MODE == self.MODE_VIDEO):
			return

		self.setUpdating(True)
		#assign your new mode
		self.MODE = self.MODE_VIDEO
		self.selectLatestThumbs(self.TYPE_VIDEO)

		self.ca.ui.updateModeChange()
		self.setUpdating(False)


	def doPhotoMode( self ):
		if (self.MODE == self.MODE_PHOTO):
			return

		self.setUpdating(True)
		#assign your new mode
		self.MODE = self.MODE_PHOTO
		self.selectLatestThumbs(self.TYPE_PHOTO)

		self.ca.ui.updateModeChange()
		self.setUpdating(False)


	def doAudioMode( self ):
		if (self.MODE == self.MODE_AUDIO):
			return

		self.setUpdating(True)
		self.MODE = self.MODE_AUDIO
		self.selectLatestThumbs(self.TYPE_AUDIO)

		self.ca.ui.updateModeChange()
		self.setUpdating(False)


	def setConstants( self ):
		#pics or vids?
		self.MODE_PHOTO = 0
		self.MODE_VIDEO = 1
		self.MODE_AUDIO = 2
		self.MODE = self.MODE_PHOTO

		self.TYPE_PHOTO = 0
		self.TYPE_VIDEO = 1
		self.TYPE_AUDIO = 2

		self.UPDATING = True
		self.RECORDING = False