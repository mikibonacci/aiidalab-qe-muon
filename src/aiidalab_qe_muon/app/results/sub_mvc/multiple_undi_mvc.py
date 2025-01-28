import ipywidgets as ipw
from aiidalab_qe.common.widgets import LoadingWidget

class MultipleUndiMVC(ipw.VBox):
    """MultipleUndiMVC class for displaying multiple UndiWidget
    
    In particular, we display the Polarization and the Kubo-Toyabe plots with respect to B_ext,
    and also an additional widget with convergence checks, if present in the calculations.
    """
    def __init__(self, undi_widget, conv_undi_widget=None):
        self.undi_widget = undi_widget
        self.conv_undi_widget = conv_undi_widget
        
        super().__init__(
            children=[LoadingWidget("Loading widgets")],
        )
        self.rendered = False
        
    def render(self,):
        if self.rendered:
            return
        
        self.children = (self.undi_widget,)
        if self.conv_undi_widget is not None:
            self.children += (self.conv_undi_widget,)
            
        for child in self.children:
            child.render()