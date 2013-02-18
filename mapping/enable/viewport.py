
from numpy import array
from traits.api import Instance, Bool, Int, Property, Float, DelegatesTo, \
                       on_trait_change
from enable.viewport import Viewport
from enable.base import empty_rectangle, intersect_bounds
from enable.enable_traits import coordinate_trait

from canvas import MappingCanvas
from zoom import MappingZoomTool

class MappingViewport(Viewport):

    component = Instance(MappingCanvas)

    zoom_level = Int(0)

    geoposition = Property(coordinate_trait, depends_on='view_position')
    latitude = Property(Float, depends_on='geoposition')
    longitude = Property(Float, depends_on='geoposition')

    tile_cache = DelegatesTo('component')
    min_level = Property(lambda self: self.tile_cache.min_level)
    max_level = Property(lambda self: self.tile_cache.max_level)

    zoom_tool = Instance(MappingZoomTool)

    enable_zoom = Bool(True)
    stay_inside = Bool(True)

    draw_cross = Bool(True)

    fit_window = True

    def __init__(self, **traits):
        # Skip parent constructor
        super(Viewport, self).__init__(**traits)
        self.zoom_tool = MappingZoomTool(self)
        if self.enable_zoom:
            self._enable_zoom_changed(False, True)

    def _get_latitude(self):
        return self.geoposition[0]
    def _set_latitude(self, val):
        self.geoposition[0] = val

    def _get_longitude(self):
        return self.geoposition[1]
    def _set_longitude(self, val):
        self.geoposition[1] = val

    def _get_geoposition(self):
        x, y = self.view_position
        w, h = self.bounds
        return self.component._screen_to_WGS84(x+w/2., y+h/2., self.zoom_level)

    def _set_geoposition(self, (lat, lon)):
        x, y = self.component._WGS84_to_screen(lat, lon, self.zoom_level)
        w, h = self.bounds
        self.view_position = [x - w/2., y - h/2.]
        self.component.request_redraw()

    def _bounds_changed(self, old, new):
        # Update position
        dw, dh = new[0]-old[0], new[1]-old[1]
        x, y = self.view_position
        self.view_position = [x - dw/2., y - dh/2.]
        super(MappingViewport, self)._bounds_changed(old, new)

    def _draw_overlay(self, gc, view_bounds=None, mode="normal"):
        if self.draw_cross:
            x, y, width, height = view_bounds
            with gc:
                # draw +
                size = 10
                gc.set_stroke_color((0,0,0,1))
                gc.set_line_width(1.0)
                cx, cy = x+width/2., y+height/2.
                gc.move_to(cx, cy-size)
                gc.line_to(cx, cy+size)
                gc.move_to(cx-size, cy)
                gc.line_to(cx+size, cy)
                gc.stroke_path()
        super(MappingViewport, self)._draw_overlay(gc, view_bounds, mode)

    def _draw_mainlayer(self, gc, view_bounds=None, mode="normal"):

        # For now, ViewPort ignores the view_bounds that are passed in...
        # Long term, it should be intersected with the view_position to
        # compute a new view_bounds to pass in to our component.
        if self.component is not None:

            x, y = self.position
            view_x, view_y = self.view_position
            with gc: 
                # Clip in the viewport's space (screen space).  This ensures
                # that the half-pixel offsets we us are actually screen pixels,
                # and it's easier/more accurate than transforming the clip
                # rectangle down into the component's space (especially if zoom
                # is involved).
                gc.clip_to_rect(x-0.5, y-0.5,
                                self.width+1,
                                self.height+1)
    
                # There is a two-step transformation from the viewport's "outer"
                # coordinates into the coordinates space of the viewed component:
                # scaling, followed by a translation.
                if self.enable_zoom:
                    if self.zoom != 0:
                        gc.scale_ctm(self.zoom, self.zoom)
                        gc.translate_ctm(x/self.zoom - view_x, y/self.zoom - view_y)
                    else:
                        raise RuntimeError("Viewport zoomed out too far.")
                else:
                    gc.translate_ctm(x - view_x, y - view_y)
    
                # Now transform the passed-in view_bounds; this is not the same thing as
                # self.view_bounds!
                if view_bounds:
                    # Find the intersection rectangle of the viewport with the view_bounds,
                    # and transform this into the component's space.
                    clipped_view = intersect_bounds(self.position + self.bounds, view_bounds)
                    if clipped_view != empty_rectangle:
                        # clipped_view and self.position are in the space of our parent
                        # container.  we know that self.position -> view_x,view_y
                        # in the coordinate space of our component.  So, find the
                        # vector from self.position to clipped_view, then add this to
                        # view_x and view_y to generate the transformed coordinates
                        # of clipped_view in our component's space.
                        offset = array(clipped_view[:2]) - array(self.position)
                        new_bounds = ((offset[0]/self.zoom + view_x),
                                      (offset[1]/self.zoom + view_y),
                                      clipped_view[2] / self.zoom, clipped_view[3] / self.zoom)
                        # FIXME This is a bit hacky - i should pass in the zoom level
                        # to the draw function
                        self.component._zoom_level = self.zoom_level
                        self.component.draw(gc, new_bounds, mode=mode)
        return

