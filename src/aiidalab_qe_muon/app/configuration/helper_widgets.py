import ipywidgets as ipw
import traitlets as tl

from aiidalab_qe.common.infobox import InfoBox

class ExternalMagneticFieldUndiWidget(ipw.HBox):
    """The widget to choose magnetic field in the undi run.
    
    """
    
    field_list = tl.List(tl.Int(),default=[])
        
    def __init__(self, title: str = "External magnetic fields (mT):", B_min=0, B_max=10, B_step_grid=2, **kwargs):
        super().__init__(**kwargs)

        self.B_range = ipw.IntRangeSlider(
            value=[B_min, B_max],
            min=0,
            max=150,
            step=1,
            description="B<sub>range</sub>:",
            disabled=False,
            continuous_update=True,
            orientation="horizontal",
            layout=ipw.Layout(width="50%"),
            
        )
        
        self.B_step_grid = ipw.BoundedIntText(
            value=B_step_grid,
            min=0,
            max=150,
            step=1,
            description="B<sub>step</sub>:",
            disabled=False,
            continuous_update=True,
            layout=ipw.Layout(width="15%"),

        )
        
        self.number_of_calcs = ipw.HTML(
            f""" Calculations per site: {self.number_of_calculations}""",
            layout=ipw.Layout(width="15%", margin='0 0 0 10px'),
        )
        
        self.layout = ipw.Layout(width="100%", justify_content="flex-start")
        
        for field in [self.B_range, self.B_step_grid]:
            ipw.dlink(
                (field, 'value'), 
                (self.number_of_calcs, 'value'), 
                lambda v: f""" Calculations per site: {self.number_of_calculations}"""
            )
            ipw.dlink(
                (field, 'value'), 
                (self, 'field_list'), 
                lambda v: [i for i in range(self.B_range.value[0], self.B_range.value[1] + 1, self.B_step_grid.value)]
            )
        
        self.children = [
            ipw.HTML(title),
            self.B_range,
            self.B_step_grid,
            #self.number_of_calcs
        ]
        
    @property
    def number_of_calculations(self):
        return int( (self.B_range.value[1] - self.B_range.value[0]) / self.B_step_grid.value + 1 )

    
    
class SettingsInfoBoxWidget(ipw.VBox):
    """TODO: Check that his is not overlapping with the in-app guides
    
    I would like to do something similar for structure viewer (like for clustering or mu spacing) and use instead of the accordion in the results.
    Maybe better to do a similar one for them
    """
    
    def __init__(self, description: str = "", info: str = "", **kwargs):
        super().__init__(**kwargs)
                
        self.about_toggle = ipw.ToggleButton(
            layout=ipw.Layout(width="auto"),
            button_style="info",
            icon="info",
            value=False,
            description=  description,
            tooltip="Info on these settings",
            disabled=False,
        )
        
        self.infobox = InfoBox(
            children=[ipw.HTML(info)],
        )
        ipw.dlink(
            (self.about_toggle, "value"), 
            (self.infobox, "layout"),
            lambda x: {"display": "block"} if x else {"display": "none"}
        )
        
        self.children = [
            ipw.HBox([self.about_toggle]),
            #self.infobox
        ]
        
        # NOTE: the self.infobox is not shown by default, but can be added in the other widget, to decide where to display it. more flexibility.