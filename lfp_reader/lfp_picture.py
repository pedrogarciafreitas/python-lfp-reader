# python
#
# lfp-reader
# LFP (Light Field Photography) File Reader.
#
# http://code.behnam.es/python-lfp-reader/
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright (C) 2012-2013  Behnam Esfahbod


"""Read and process LFP Picture files
"""


import sys
import math
from struct import unpack
from collections import namedtuple
from cStringIO import StringIO

import lfp_file

# Python Imageing Library
try:
    import Image as PIL
except ImportError:
    PIL = None
def _check_pil_module():
    if PIL is None:
        raise RuntimeError("Cannot find Python Imaging Library (PIL or Pillow)")

# GStreamer Python
try:
    import gst_h264_splitter
except ImportError:
    gst_h264_splitter = None
def _check_gst_h264_splitter_module():
    if gst_h264_splitter is None:
        raise RuntimeError("Cannot find GStreamer Python library")


################################################################
# Picture file

class LfpPictureError(lfp_file.LfpGenericError):
    """LFP Picture file error"""


def _lfp_picture_data_class(cls_name, *args):
    """Store formatted data for LFP Picture file"""
    return namedtuple(cls_name, *args)

Frame = _lfp_picture_data_class('Frame',
        'metadata image private_metadata')

RefocusStack = _lfp_picture_data_class('RefocusStack',
        'refocus_images depth_lut default_lambda default_width default_height')

RefocusImage = _lfp_picture_data_class('RefocusImage',
        'id lambda_ width height representation chunk data')

ParallaxStack = _lfp_picture_data_class('ParallaxStack',
        'parallax_images default_width default_height viewpoint_width viewpoint_height')

ParallaxImage = _lfp_picture_data_class('ParallaxImage',
        'id coord width height representation chunk data')

DepthLut = _lfp_picture_data_class('DepthLut',
        'width height representation table chunk')

Coord = _lfp_picture_data_class('Coord',
        'x y')


class LfpPictureFile(lfp_file.LfpGenericFile):
    """Load an LFP Picture file and read the data chunks on-demand
    """

    ################################
    # Internals

    def __init__(self, file_path):
        lfp_file.LfpGenericFile.__init__(self, file_path)
        self._frame = None
        self._refocus_stack = None
        self._parallax_stack = None
        self._pil_cache = {}

    def __repr__(self):
        version = self.meta.content['version']
        image_size = self._frame.image.size if self._frame else 'N/A'
        return ("LfpPictureFile(version=%s.%s, provisionalDate=%s, frame=%s)" % (
            version['major'], version['minor'],
            version['provisionalDate'],
            'True' if self._frame else 'False'
            ))

    ################################
    # Loading

    def process(self):
        try:
            picture_data = self.meta.content['picture']
            frame_data = picture_data['frameArray'][0]['frame']

            # Data for raw picture file
            if (    frame_data['metadataRef']        in self.chunks and
                    frame_data['imageRef']           in self.chunks and
                    frame_data['privateMetadataRef'] in self.chunks ):
                self._frame = Frame(
                        metadata=        self.chunks[frame_data['metadataRef']],
                        image=           self.chunks[frame_data['imageRef']],
                        private_metadata=self.chunks[frame_data['privateMetadataRef']])

            # Data for processed picture file
            if picture_data['accelerationArray']:
                for accel_data in picture_data['accelerationArray']:
                    accel_type    = accel_data["type"]
                    accel_content = accel_data['vendorContent']

                    if accel_type == 'com.lytro.acceleration.refocusStack':
                        if 'imageArray' in accel_content:
                            # JPEG-based refocus stack
                            refocus_images = { id: RefocusImage(
                                id=id,
                                lambda_=rimg['lambda'],
                                width=rimg['width'],
                                height=rimg['height'],
                                representation=rimg['representation'],
                                chunk=self.chunks[rimg['imageRef']],
                                data=None)
                                for id, rimg in enumerate(accel_content['imageArray']) }

                        elif 'blockOfImages' in accel_content:
                            block_of_images = accel_content['blockOfImages']
                            if block_of_images['representation'] == 'h264':
                                # H264-encoded refocus stack
                                _check_gst_h264_splitter_module()
                                images_representation = 'jpeg'
                                h264_data = self.chunks[block_of_images['blockOfImagesRef']].data
                                h264_splitter = gst_h264_splitter.H246Splitter(h264_data, image_format=images_representation)
                                images_data = h264_splitter.get_images()
                                refocus_images = { id: RefocusImage(
                                    id=id,
                                    lambda_=rimg['lambda'],
                                    width=rimg['width'],
                                    height=rimg['height'],
                                    representation=images_representation,
                                    chunk=None,
                                    data=images_data[id])
                                    for id, rimg in enumerate(block_of_images['metadataArray']) }

                            else:
                                raise KeyError('Unsupported Processed LFP Picture file')

                        else:
                            raise KeyError('Unsupported Processed LFP Picture file')

                        # Depth Look-up Table
                        depth_width  = accel_content['depthLut']['width']
                        depth_height = accel_content['depthLut']['height']
                        depth_data  = self.chunks[accel_content['depthLut']['imageRef']].data
                        depth_table = [ [
                            unpack("f", depth_data[ (j*depth_width + i) * 4 : (j*depth_width + i+1) * 4 ])[0]
                            for j in xrange(depth_height) ]
                            for i in xrange(depth_width) ]

                        depth_lut = DepthLut(
                                width=depth_width,
                                height=depth_height,
                                representation=accel_content['depthLut']['representation'],
                                table=depth_table,
                                chunk=self.chunks[accel_content['depthLut']['imageRef']])

                        default_dimensions = accel_content['displayParameters']['displayDimensions']['value']
                        self._refocus_stack = RefocusStack(
                            default_lambda=accel_content['defaultLambda'],
                            default_width=default_dimensions['width'],
                            default_height=default_dimensions['height'],
                            refocus_images=refocus_images,
                            depth_lut=depth_lut)

                    elif accel_type == 'com.lytro.acceleration.edofParallax':
                        # H264-based Extended Depth of Field Parallax
                        block_of_images = accel_content['blockOfImages']
                        if block_of_images['representation'] == 'h264':
                            # H264-encoded parallax stack
                            _check_gst_h264_splitter_module()
                            images_representation = 'jpeg'
                            h264_data = self.chunks[block_of_images['blockOfImagesRef']].data
                            h264_splitter = gst_h264_splitter.H246Splitter(h264_data, image_format=images_representation)
                            images_data = h264_splitter.get_images()
                            parallax_images = { id: ParallaxImage(
                                id=id,
                                coord=Coord(**pimg['coord']),
                                width=pimg['width'],
                                height=pimg['height'],
                                representation=images_representation,
                                chunk=None,
                                data=images_data[id])
                                for id, pimg in enumerate(block_of_images['metadataArray']) }

                        max_coord_x_i = max(parallax_images, key=lambda id: parallax_images[id].coord.x)
                        max_coord_y_i = max(parallax_images, key=lambda id: parallax_images[id].coord.y)
                        default_dimensions = accel_content['displayParameters']['displayDimensions']['value']
                        self._parallax_stack = ParallaxStack(
                            default_width    = default_dimensions['width'],
                            default_height   = default_dimensions['height'],
                            parallax_images  = parallax_images,
                            viewpoint_width  = 2 * parallax_images[max_coord_x_i].coord.x,
                            viewpoint_height = 2 * parallax_images[max_coord_y_i].coord.y)

                    elif accel_type == 'com.lytro.acceleration.depthMap':
                        # Depth-Map
                        #todo process depthMap
                        pass

        except KeyError:
            raise LfpPictureError("Not a valid/supported LFP Picture file")

    def get_frame(self):
        if not self._frame:
            raise LfpPictureError("%s: Not a valid/supported Raw LFP Picture file" % self.file_path)
        return self._frame

    def get_refocus_stack(self):
        if not self._refocus_stack or not self._refocus_stack.refocus_images:
            raise LfpPictureError("%s: Cannot find refocus data in LFP Picture file" % self.file_path)
        return self._refocus_stack

    def get_parallax_stack(self):
        if not self._parallax_stack or not self._parallax_stack.parallax_images:
            raise LfpPictureError("%s: Cannot find parallax data in LFP Picture file" % self.file_path)
        return self._parallax_stack


    ################################
    # Exporting

    def export(self):
        if self._frame:
            self.export_frame()
        if self._refocus_stack:
            self.export_refocus_stack()
        if self._parallax_stack:
            self.export_parallax_stack()

    def export_frame(self):
        self._frame.metadata.export_data(self.get_export_path('frame_metadata', 'json'))
        self._frame.image.export_data(self.get_export_path('frame', 'raw'))
        self._frame.private_metadata.export_data(self.get_export_path('frame_private_metadata', 'json'))

    def export_refocus_stack(self):
        for id, rimg in self._refocus_stack.refocus_images.iteritems():
            r_image_name = 'refocus_%02d' % id
            if rimg.chunk:
                rimg.chunk.export_data(self.get_export_path(r_image_name, rimg.representation))
            else:
                self.export_write(r_image_name, rimg.representation, rimg.data)

        self._refocus_stack.depth_lut.chunk.export_data(self.get_export_path('depth_lut',
            self._refocus_stack.depth_lut.representation))
        self.export_write('depth_lut', 'txt', self.get_depth_lut_txt())

    def export_parallax_stack(self):
        for id, pimg in self._parallax_stack.parallax_images.iteritems():
            r_image_name = 'parallax_%02d' % id
            if pimg.chunk:
                pimg.chunk.export_data(self.get_export_path(r_image_name, pimg.representation))
            else:
                self.export_write(r_image_name, pimg.representation, pimg.data)

    def export_all_focused(self, export_format='jpeg'):
        pil_all_focused_image = self.get_pil_image('all_focused')
        output = StringIO()
        pil_all_focused_image.save(output, export_format)
        self.export_write('all_focused', export_format, output.getvalue())
        output.close()

    def get_depth_lut_txt(self):
        depth_lut = self._refocus_stack.depth_lut
        txt = ""
        for i in xrange(depth_lut.width):
            for j in xrange(depth_lut.height):
                txt += "%9f " % depth_lut.table[j][i]
            txt += "\r\n"
        return txt


    ################################
    # Printing

    def print_info(self):
        print "    Frame:"
        if self._frame:
            print "\t%-20s\t%12d" % ("metadata:", self._frame.metadata.size)
            print "\t%-20s\t%12d" % ("image:", self._frame.image.size)
            print "\t%-20s\t%12d" % ("private_metadata:", self._frame.private_metadata.size)
        else:
            print "\tNone"

        print "    Refocus-Stack:"
        if self._refocus_stack:
            print "\t%-20s\t%12d" % ("refocus_images#:", len(self._refocus_stack.refocus_images))
            print "\t%-20s\t%12s" % ("depth_lut:", "%dx%d" %
                    (self._refocus_stack.depth_lut.width, self._refocus_stack.depth_lut.height))
            print "\t%-20s\t%12d" % ("default_lambda:", self._refocus_stack.default_lambda)
            print "\t%-20s\t%12d" % ("default_width:", self._refocus_stack.default_width)
            print "\t%-20s\t%12d" % ("default_height:", self._refocus_stack.default_height)
            print "\tAvailable Focus Depth:"
            print "\t\t",
            for id, rimg in self._refocus_stack.refocus_images.iteritems():
                print "%5.2f" % rimg.lambda_,
            print
            '''NOTE Depth Table is too big in new files to be shown as text
            print "\tDepth Table:"
            for i in xrange(self._refocus_stack.depth_lut.width):
                print "\t\t",
                for j in xrange(self._refocus_stack.depth_lut.height):
                    print "%5.2f" % self._refocus_stack.depth_lut.table[j][i],
            '''
        else:
            print "\tNone"


    ################################
    # Processing, Common

    def get_pil_image(self, group, image_id=None):
        """Cache and return a PIL.Image instances

        Parameter `group' shall be one of ('refocus', 'parallax', 'all_focused')
        """
        _check_pil_module()
        if group not in ('refocus', 'parallax', 'all_focused'):
            raise KeyError('Unknown PIL cache group: %s' % group)
        cache = self._pil_cache
        if group not in cache:
            cache[group] = {}

        if group == 'all_focused' and image_id is None:
            image_id = '_'
            if image_id not in cache[group]:
                cache[group][image_id] = self._gen_pil_all_focused_image()
            return cache[group][image_id]

        if group == 'refocus' and image_id is not None:
            img = self.get_refocus_stack().refocus_images[image_id]
        elif group == 'parallax' and image_id is not None:
            img = self.get_parallax_stack().parallax_images[image_id]
        else:
            raise KeyError('Invalid image_id: %s' % image_id)

        if image_id not in cache[group]:
            data = img.data if img.data else img.chunk.data
            cache[group][image_id] = PIL.open(StringIO(data))
        return cache[group][image_id]


    ################################
    # Processing Refocus Stack

    def find_closest_refocus_image(self, x_f=.5, y_f=.5):
        """Parameters `x_f` and `y_f` are floats in range [0, 1)
        """
        rstk = self.get_refocus_stack()
        return self.find_closest_refocus_image_by_lut_idx(
                x_f * rstk.depth_lut.width,
                y_f * rstk.depth_lut.height)

    def find_closest_refocus_image_by_lut_idx(self, ti, tj):
        """Parameters `ti` and `tj` are indices of the depth look-up table
        """
        rstk = self.get_refocus_stack()
        ti = max(0, min(int(math.floor(ti)), rstk.depth_lut.width-1))
        tj = max(0, min(int(math.floor(tj)), rstk.depth_lut.height-1))
        taget_lambda = rstk.depth_lut.table[ti][tj]
        closest_image_id = min(rstk.refocus_images,
                key=lambda id: math.fabs(rstk.refocus_images[id].lambda_ - taget_lambda))
        return rstk.refocus_images[closest_image_id]

    def _gen_pil_all_focused_image(self):
        """Return PIL.Image instance collaged from refocus images
        """
        _check_pil_module()
        rstk = self.get_refocus_stack()
        depth_lut = rstk.depth_lut
        r_images  = rstk.refocus_images
        width     = rstk.default_width
        height    = rstk.default_height

        init_data = r_images[0].data if r_images[0].data else r_images[0].chunk.data
        pil_all_focused_image = PIL.open(StringIO(init_data))

        for i in xrange(depth_lut.width):
            for j in xrange(depth_lut.height):
                box = (int(math.floor(width  * i / depth_lut.width)),
                       int(math.floor(height * j / depth_lut.height)),
                       int(math.floor(width  * (i+1) / depth_lut.width)),
                       int(math.floor(height * (j+1) / depth_lut.height)))
                closest_image = self.find_closest_refocus_image_by_lut_idx(i, j)
                pil_all_focused = self.get_pil_image('refocus', closest_image.id)
                piece = pil_all_focused.crop(box)
                pil_all_focused_image.paste(piece, box)
        return pil_all_focused_image


    ################################
    # Processing Parallax Stack

    def find_closest_parallax_image(self, x_f=.5, y_f=.5):
        """Parameters `x_f` and `y_f` are floats in range [0, 1)
        """
        pstk = self.get_parallax_stack()
        viewpoint_coord = Coord((x_f-.5) * pstk.viewpoint_width,
                                (y_f-.5) * pstk.viewpoint_height)
        closest_image, min_euclidean_dist = None, sys.maxint
        for id, pimg in pstk.parallax_images.iteritems():
            euclidean_dist = ( (pimg.coord.x-viewpoint_coord.x)**2
                             + (pimg.coord.y-viewpoint_coord.y)**2 )
            if euclidean_dist < min_euclidean_dist:
                closest_image, min_euclidean_dist = pimg, euclidean_dist
        return closest_image

