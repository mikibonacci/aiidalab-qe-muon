"""Bands results view widgets

"""
from __future__ import annotations


from widget_bandsplot import BandsPlotWidget

from aiidalab_qe.common.panel import ResultPanel

import numpy as np

from ..utils.raman.result import export_iramanworkchain_data
from ..utils.harmonic.result import export_phononworkchain_data

class Result(ResultPanel):

    title = "Vibrational Structure"
    workchain_label = "iraman"

    def _update_view(self):
                
        spectra_data = export_iramanworkchain_data(self.node)
        phonon_data = export_phononworkchain_data(self.node)

        if spectra_data:
            if spectra_data[3] in ["Raman vibrational spectrum","Infrared vibrational spectrum"]:
                import plotly.graph_objects as go

                frequencies = spectra_data[1]
                total_intensities = spectra_data[0]
                
                g = go.FigureWidget(
                    layout=go.Layout(
                        title=dict(text=spectra_data[3]),
                        barmode="overlay",
                    )
                )
                g.layout.xaxis.title = "Wavenumber (cm-1)"
                g.layout.yaxis.title = "Intensity (arb. units)"
                g.layout.xaxis.nticks = 0 
                g.add_scatter(x=frequencies,y=total_intensities,name=f"")

                
                self.children=[g]
        
        if phonon_data:    
            if phonon_data[2] == 'bands':
                _bands_plot_view = BandsPlotWidget(
                    bands=[phonon_data[0]],
                    **phonon_data[1],
                )
                self.children=[_bands_plot_view]
                
            elif phonon_data[2] == 'dos':
                _bands_plot_view = BandsPlotWidget(
                dos=phonon_data[0],
                plot_fermilevel=False,
                show_legend=False,
                **phonon_data[1],
                )
                self.children=[_bands_plot_view]

            elif phonon_data[2] == 'thermal':
                import plotly.graph_objects as go

                T = phonon_data[0][0]
                F = phonon_data[0][1]
                F_units = phonon_data[0][2]
                E = phonon_data[0][3]
                E_units = phonon_data[0][4]
                Cv = phonon_data[0][5]
                Cv_units = phonon_data[0][6]

                g = go.FigureWidget(
                    layout=go.Layout(
                        title=dict(text="Thermal properties"),
                        barmode="overlay",
                    )
                )
                g.layout.xaxis.title = "Temperature (K)"
                g.add_scatter(x=T,y=F,name=f"Helmoltz Free Energy ({F_units})")
                g.add_scatter(x=T,y=E,name=f"Entropy ({E_units})")
                g.add_scatter(x=T,y=Cv,name=f"Specific Heat-V=const ({Cv_units})")

                self.children=[g]





