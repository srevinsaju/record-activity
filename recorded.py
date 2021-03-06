# Copyright (C) 2008, Media Modifications Ltd.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import os
from gi.repository import GdkPixbuf

import constants
from instance import Instance
import utils
import serialize


class Recorded:
    def __init__(self):
        self.type = -1
        self.time = None
        self.recorderName = None
        self.recorderHash = None
        self.title = None
        self.colorStroke = None
        self.colorFill = None
        self.mediaMd5 = None
        self.thumbMd5 = None
        self.mediaBytes = None
        self.thumbBytes = None
        self.tags = None

        # flag to alert need to re-datastore the title
        self.metaChange = False

        # when you are datastore-serialized, you get one of these ids...
        self.datastoreId = None
        self.datastoreOb = None

        # if not from the datastore, then your media is here...
        self.mediaFilename = None
        self.thumbFilename = None
        self.audioImageFilename = None
        self.videoImageFilename = None

        # for flagging when you are being saved to the datastore for
        # the first time...  and just because you have a datastore id,
        # doesn't mean you're saved
        self.savedMedia = False
        self.savedXml = False

        # assume you took the picture
        self.buddy = False
        self.downloadedFromBuddy = False
        self.triedMeshBuddies = []
        self.meshDownloading = False
        self.meshDownloadingFrom = ""
        self.meshDownloadingFromNick = ""
        self.meshDownlodingPercent = 0.0
        self.meshDownloadingProgress = False
        # if someone is downloading this, then hold onto it
        self.meshUploading = False
        self.meshReqCallbackId = 0

        self.deleted = False

    def setTitle(self, newTitle):
        if self.title == newTitle:
            return
        self.title = newTitle
        self.metaChange = True

    def setTags(self, newTags):
        self.tags = newTags
        self.metaChange = True

    def isClipboardCopyable(self):
        if self.buddy:
            if not self.downloadedFromBuddy:
                return False
        return True

    # scenarios:
    # launch, your new thumb    -- Journal/session
    # launch, your new media    -- Journal/session
    # launch, their new thumb   -- Journal/session/buddy
    # launch, their new media   -- ([request->]) Journal/session/buddy
    # relaunch, your old thumb  -- metadataPixbuf on request (or save to
    #                              Journal/session..?)
    # relaunch, your old media  -- datastoreObject->file (hold onto the
    #                              datastore object, delete if deleted)
    # relaunch, their old thumb -- metadataPixbuf on request (or save to
    #                              Journal/session..?)
    # relaunch, their old media -- datastoreObject->file (hold onto the
    #                              datastore object, delete if deleted) |
    #                              ([request->]) Journal/session/buddy
    def getThumbPixbuf(self):
        thumbFilepath = self.getThumbFilepath()
        if thumbFilepath and os.path.isfile(thumbFilepath):
            return GdkPixbuf.Pixbuf.new_from_file(thumbFilepath)
        else:
            return None

    def getThumbFilepath(self):
        if not self.thumbFilename:
            return None
        return os.path.join(Instance.instancePath, self.thumbFilename)

    def make_thumb_path(self):
        thumbFilename = self.mediaFilename + "_thumb.jpg"
        thumbFilepath = os.path.join(Instance.instancePath, thumbFilename)
        thumbFilepath = utils.getUniqueFilepath(thumbFilepath, 0)
        self.thumbFilename = os.path.basename(thumbFilepath)
        return self.getThumbFilepath()

    def getAudioImagePixbuf(self):
        audioPixbuf = None

        if self.audioImageFilename is None:
            audioPixbuf = self.getThumbPixbuf()
        else:
            audioFilepath = self.getAudioImageFilepath()
            if (audioFilepath is not None):
                audioPixbuf = GdkPixbuf.Pixbuf.new_from_file(audioFilepath)

        return audioPixbuf

    def getAudioImageFilepath(self):
        if self.audioImageFilename is not None:
            audioFilepath = os.path.join(Instance.instancePath,
                                         self.audioImageFilename)
            return os.path.abspath(audioFilepath)
        else:
            return self.getThumbFilepath()

    def getVideoImagePixbuf(self):
        videoPixbuf = None

        if self.videoImageFilename is None:
            videoPixbuf = self.getThumbPixbuf()
        else:
            videoFilepath = self.getVideoImageFilepath()
            if (videoFilepath is not None):
                videoPixbuf = GdkPixbuf.Pixbuf.new_from_file(videoFilepath)

        return videoPixbuf

    def getVideoImageFilepath(self):
        if self.videoImageFilename is not None:
            videoFilepath = os.path.join(Instance.instancePath,
                                         self.videoImageFilename)
            return os.path.abspath(videoFilepath)
        else:
            return self.getThumbFilepath()

    def getMediaFilepath(self):
        if self.datastoreId is None:
            if not self.buddy:
                # just taken by you, so it is in the tempSessionDir
                mediaFilepath = os.path.join(Instance.instancePath,
                                             self.mediaFilename)
                return os.path.abspath(mediaFilepath)
            else:
                if self.downloadedFromBuddy:
                    # the user has requested the high-res version, and
                    # it has downloaded
                    mediaFilepath = os.path.join(Instance.instancePath,
                                                 self.mediaFilename)
                    return os.path.abspath(mediaFilepath)
                else:
                    if self.mediaFilename is None:
                        # creating a new filepath, probably just got
                        # here from the mesh
                        ext = constants.MEDIA_INFO[self.type]['ext']
                        recdPath = os.path.join(Instance.instancePath,
                                                "recdFile_" + self.mediaMd5 +
                                                "." + ext)
                        recdPath = utils.getUniqueFilepath(recdPath, 0)
                        self.mediaFilename = os.path.basename(recdPath)
                        mediaFilepath = os.path.join(Instance.instancePath,
                                                     self.mediaFilename)
                        return os.path.abspath(mediaFilepath)
                    else:
                        mediaFilepath = os.path.join(Instance.instancePath,
                                                     self.mediaFilename)
                        return os.path.abspath(mediaFilepath)

        else:
            # pulling from the datastore, regardless of who took it,
            # cause we got it first, get the datastoreObject and hold
            # the reference in this Recorded instance
            if self.datastoreOb is None:
                self.datastoreOb = serialize.getMediaFromDatastore(self)
            if self.datastoreOb is None:
                print("RecordActivity error -- unable to "
                      "get datastore object in getMediaFilepath")
                return None

            return self.datastoreOb.file_path

    def getCopyClipboardPixbuf(self):
        if self.type == constants.TYPE_PHOTO:
            return GdkPixbuf.Pixbuf.new_from_file(self.getMediaFilepath())
        if self.type == constants.TYPE_VIDEO:
            return self.getVideoImagePixbuf()
        if self.type == constants.TYPE_AUDIO:
            return self.getAudioImagePixbuf()
        return None
