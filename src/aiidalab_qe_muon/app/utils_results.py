from aiida import orm

import base64
import numpy as np
import pandas as pd

import ipywidgets as ipw
import plotly.graph_objects as go
import traitlets

from aiidalab_widgets_base.viewers import StructureDataViewer

from pymatgen.core import Structure


#### for KT

from ase.io import read
from ase import neighborlist

from importlib_resources import files
from aiidalab_qe_muon.app import data

file = files(data)/'isotopedata.txt'

info = pd.read_table(file,comment='%', 
                     delim_whitespace=True, 
                     names = ["Z","A","Stable", "Symbol", 
                              "Element", "Spin", "G_factor", 
                              "Abundance", "Quadrupole"])

munhbar = 7.622593285e6*2*np.pi # mu_N/hbar, SI
#(2/3)(μ_0/4pi)^2 (planck2pi 2pi × 135.5 MHz/T )^2 = 5.374 021 39 × 10^(−65) kg²·m^(6)·A^(−2)·s^(−4)
factor = 5.37402139E-5 # angstrom instead of m

def get_isotopes(Z):
    return info[info.Z==Z][['Abundance','Spin','G_factor']].to_numpy()



def compute_second_moments(atms, cutoff_distances = {}):
    """
    Compute second moments taking care of isotope averages
    """
    tot_H = np.count_nonzero(atms.get_atomic_numbers() == 1)
    
    species_avg = {}
    for e in np.unique(atms.get_atomic_numbers()):
        if e == 1:
            continue
    
        species_avg[e] = 0.0
        for a in get_isotopes(e):
            species_avg[e] += (a[0]/100) * a[1]*(a[1]+1) * (munhbar*a[2])**2
    
    # compute second moments
    specie_contribs = {}
    for e in np.unique(atms.get_atomic_numbers()):
        if e == 1:
            continue
        sum = 0.5 * np.sum(neighborlist.neighbor_list('d',atms, cutoff={(1,e): cutoff_distances.get(e, 40)})**-6)
        specie_contribs[e] = species_avg[e] * sum * factor / tot_H

    return specie_contribs


import matplotlib.pyplot as plt

def kubo_toyabe(tlist, Gmu_S2):
        """Calculates the Kubo-Toyabe polarization for the nuclear arrangement
        provided in input.
    
        Parameters
        ----------
        tlist : numpy.array
            List of times at which the muon polarization is observed.
    
        Returns
        -------
        numpy.array
            Kubo-Toyabe function, for a powder in zero field.
        """
        # this is gamma_mu times sigma^2
        return 0.333333333333 + 0.6666666666 * \
                (1- Gmu_S2  *  np.power(tlist,2)) * \
                np.exp( - 0.5 * Gmu_S2 * np.power(tlist,2))

#### end for KT

change_names_for_html = {
        #"tot_energy":"total energy (eV)",
        "muon_position_cc":"muon position (crystal coordinates)",
        "delta_E":"ΔE<sub>total</sub> (eV)",
        
        "structure":"structure pk",
        
        "B_T":"B<sub>total</sub> (T)",
        "Bdip":"B<sub>dipolar</sub> (T)",
        "hyperfine":"B<sub>hyperfine</sub> (T)",

        "B_T_norm":"|B<sub>total</sub>| (T)",
        "Bdip_norm":"|B<sub>dip</sub>| (T)",
        "hyperfine_norm":"|B<sub>hyperfine</sub>| (T)",
    }


#(1) pandas.
def produce_muonic_dataframe(findmuon_output_node):

    bars = {
        "magnetic_units":"tesla",
        "magnetic_keys":["B_T","Bdip","B_T_norm","hyperfine_norm","hyperfine","Bdip_norm"],
        "muons":{}
    }
    for idx, uuid in findmuon_output_node.all_index_uuid.get_dict().items():
        if idx in findmuon_output_node.unique_sites.get_dict().keys():
            relaxwc = orm.load_node(uuid)
            bars["muons"][idx] = {}
            bars["muons"][idx]['tot_energy'] = relaxwc.outputs.output_parameters.get_dict()["energy"]
            bars["muons"][idx]['structure'] = relaxwc.outputs.output_structure
            bars["muons"][idx]['muon_index'] = idx
            bars["muons"][idx]['muon_position_cc'] = list(
                np.round(np.array(
                    findmuon_output_node.unique_sites.get_dict()[idx][0]["sites"][-1]["abc"]
                    ),3),
            )

    if "unique_sites_dipolar" in findmuon_output_node:
        for configuration in findmuon_output_node.unique_sites_dipolar.get_list():
            for B in ["B_T","Bdip"]:
                bars["muons"][str(configuration["idx"])][B] = list(np.round(np.array(configuration[B]),3))
                if B in ["B_T"]:
                    bars["muons"][str(configuration["idx"])]["B_T_norm"] = round(np.linalg.norm(np.array(configuration[B])),3)
                if B in ["Bdip"]:
                    bars["muons"][str(configuration["idx"])]["Bdip_norm"] = round(np.linalg.norm(np.array(configuration[B])),3)
            if "unique_sites_hyperfine" in findmuon_output_node:
                v = findmuon_output_node.unique_sites_hyperfine.get_dict()[str(configuration["idx"])]
                #bars["muons"][str(configuration["idx"])]["hyperfine"] = v
                bars["muons"][str(configuration["idx"])]["hyperfine_norm"] = round(abs(v[-1]),3) #<-- we select the last, is in T (the first is in Atomic units).
    
    #<HERE>: filter only unique sites.
    #</HERE>
    df = pd.DataFrame.from_dict(bars["muons"])

    #sort
    df = df.sort_values("tot_energy",axis=1)

    #deltaE
    df.loc["delta_E"] = df.loc["tot_energy"] - df.loc["tot_energy"].min()
    return df
    

#(2) unit cell with all muonic sites.

def produce_collective_unit_cell(findmuon_output_node):
    
    #e_min=np.min([qeapp_node.outputs.unique_sites.get_dict()[key][1] for key in qeapp_node.outputs.unique_sites.get_dict()])
    sc_matrix=[findmuon_output_node.all_index_uuid.creator.caller.inputs.sc_matrix.get_list()] #WE NEED TO HANDLE also THE CASE IN WHICH IS GENERATED BY MUSCONV.
    input_str = findmuon_output_node.all_index_uuid.creator.caller.inputs.structure.get_pymatgen().copy()

    #append tags to recognize the muon site.
    input_str.tags = [None]*input_str.num_sites

    for key in findmuon_output_node.unique_sites.get_dict() :
        #print("H"+key, qeapp_node.outputs.unique_sites.get_dict()[key][1], (qeapp_node.outputs.unique_sites.get_dict() [key][1]-e_min))
        #fo.write("%s %16f %16f \n "%  ("H"+key, uniquesites_dict[key][1], (uniquesites_dict[key][1]-e_min)))
        py_struc = Structure.from_dict(findmuon_output_node.unique_sites.get_dict()[key][0])
        musite = py_struc.frac_coords[py_struc.atomic_numbers.index(1)]
        mupos = np.dot(musite,sc_matrix)%1
        input_str.append(species = "H"+key, coords = mupos[0], coords_are_cartesian = False, validate_proximity = True)
        input_str.tags.append(key)
    
    l = []
    for i in input_str.sites:
        i.properties["kind_name"] = i.label
        l.append(i.properties)
    #raise ValueError(l)
        
    return input_str


###############start single muon site widgets #####################################      
class SingleMuonBarPlotWidget(ipw.VBox):
    """
    Widget for the bar plots for a single muon site.
    
    Inputs:
    df: the pandas dataframe with all the collected results
    selected: the index of the selected muon site, linked to the dropdown.
    """
    
    #needed to be observed.
    selected = traitlets.Instance(str, allow_none=True)
    
    def __init__(
        self,
        df,
        selected="1",  
        **kwargs):
        
        self.fig = go.FigureWidget()
        
        self.df = df
        self.selected = selected
        
        #figure widget
        
        ## Checking if we have the fields in the outputs.
        ### we may also have nothing, or not thed hyperfine.
        self.labels=[]
        self.entries=[]
        for entry in ['B_T_norm','Bdip_norm','hyperfine_norm']:
            if entry in self.df.index.tolist():
                self.entries.append(entry)
                self.labels.append(change_names_for_html[entry])
        
        
        ## adding the trace
        colors = ["blue","red","green"][:len(self.entries)]
        self.fig.add_trace(
            go.Bar(
                x = self.labels,
                y = self.df[self.selected][self.entries].tolist(),
                marker=dict(
                color=colors,
                opacity=0.5
                ),
            ),
        )
    
        #updating the layout.
        # Add labels and titles
        self.fig.update_layout(
            barmode="overlay",
            xaxis_title='Contributions',
            yaxis_title='Field magnitude (T)',
            #xaxis=dict(title='City', tickangle=45), # Customize x-axis
            #yaxis=dict(title='Population'), # Customize y-axis

            #width=500, # Width of the plot
            #height=500, # Height of the plot

            font=dict( # Font size and color of the labels
                size=12,
                color='#333333',
            ),
            plot_bgcolor='gainsboro', # Background color of the plot
            #paper_bgcolor='white', # Background color of the paper

            bargap=0.001, # Gap between bars
            bargroupgap=0.01, # Gap between bar groups
        )
        
        #observe the selected, so we can link
        self.observe(self._observe_selected,"selected")
        
        super().__init__(children=[self.fig],**kwargs)

    def _observe_selected(self, change):
        #if the selected value changes, we update data for the trace, 
        #or better we update the y values of each trace.
        self.fig.data[0].y = self.df[self.selected][self.entries].tolist()


class SingleSupercellTableWidget(ipw.VBox):
    
    #needed to be observed.
    selected = traitlets.Instance(str, allow_none=True)
    
    def __init__(self,df,selected="1",**kwargs):
        
        self.df = df
        self.selected = selected
        self.data = self.df[self.selected].to_dict()
        
        table_html = self._generate_html_table()
        self.table_widget = ipw.VBox([ipw.HTML(value=f"<b> Data for muon site #{self.selected}</b>"),
                                      ipw.HTML(value=table_html)])
        
        #observe the selected, so we can link
        self.observe(self._observe_selected,"selected")
        
        super().__init__(children=[self.table_widget],**kwargs)
        
    def _generate_html_table(self):
        if not self.selected: 
            return ""
        #headers
        table_html = '<table style="width:100%; border:1 solid black;">'
        table_html += "<tr>"
        table_html += "<td style='text-align:center;'> <b>Entry</b> </td>"
        table_html += "<td style='text-align:center;'> <b>Value</b> </td>"
        table_html += "</tr>"

        #data
        for k,v in change_names_for_html.items():
            if k in self.data.keys(): # may not contain some magnetic info like hyperfine
                table_html += "<tr>"
                table_html += "<td style='text-align:center;'>{}</td>".format(v)
                value = round(self.data[k],3) if k == "delta_E" else self.data[k] 
                value = value.pk if k == "structure" else value
                table_html += "<td style='text-align:center;'>{}</td>".format(value)
                table_html += "</tr>"
        table_html += "</table>"
        
        payload = base64.b64encode(self.df[self.selected].to_csv(index=True).encode()).decode()
        fname = f"muon_{self.selected}.csv"
        table_html += f"""Download table in csv format: <a download="{fname}"
        href="data:text/csv;base64,{payload}" target="_blank">{fname}</a>"""

        return table_html
    
    def _observe_selected(self, change):
        #we update the children of the table_widget.
        self.data = self.df[self.selected].to_dict()
        table_html = self._generate_html_table()
        self.table_widget.children = [ipw.HTML(value=f"<b> Data for muon site #{self.selected}</b>"),ipw.HTML(value=table_html)]


class SingleMuonStructureBarWidget(ipw.VBox):
        
    def __init__(self, df=None, selected="1",**kwargs):
        
        self.df = df
        self.selected = selected
        
        self.muon_index_list = df.columns.tolist()
        self.muon_index_list.sort()
        
        if len(self.df)>0: 
            """
            Structure of the widget:
            
            dropdown
            structureviewer
            barplot+table
            """
            dropdown = ipw.Dropdown(
                options=[None]+self.muon_index_list,
                value=None,

            )
            dropdown.observe(self._update_view, names='value')

            dropdown_label = ipw.HTML("Select muon site:")

            dropdown_widget = ipw.HBox(children=[dropdown_label,dropdown])
            
            self.child1=StructureDataViewer(structure=self.df[self.selected]["structure"])
            
            #in an HBox:
            self.child3=SingleSupercellTableWidget(self.df, self.selected)
            children_2_3 = [self.child3]
            if "B_T" in self.df.index:
                self.child2=SingleMuonBarPlotWidget(self.df, self.selected)
                children_2_3 = [self.child2, self.child3]

            children = [
                dropdown_widget,
                ipw.VBox([
                    self.child1,
                    ipw.HBox(children=children_2_3)])]
        else:
            children = []
            
        super().__init__(children, **kwargs)
        
    def _update_view(self,change):
        #we just update the selected of each child, which is observed in the corresponding widget(child).
        if change.new != change.old:
            if not change.new: 
                pass
            else:
                self.child1.structure = self.df[change["new"]]["structure"].get_ase()
                if hasattr(self,"child2"): self.child2.selected = change["new"]
                self.child3.selected = change["new"]


###############end single muon site widgets #####################################

###############start summary muon sites widgets #####################################
class KT_asymmetry_widget(ipw.HBox):
    
    def __init__(
        self,
        df,
        selected=None,  
        **kwargs):
        
        self.fig = go.FigureWidget()
        self.df=df
        self.KT = {}
        self.t = np.linspace(0,40e-6,1000) #should be a slider
        self.t_axes = np.linspace(0,40,1000) #should be a slider
        self.selected = selected


        #figure widget
        ## the scatter plots.
        for data,label in zip(df.loc["structure"].tolist(),df.loc["muon_index"].tolist()):
            atms = data.get_ase()

            
            sm = compute_second_moments(atms)
            self.KT[label] = kubo_toyabe(self.t, np.sum(list(sm.values())))
        
    
        for label,data in self.KT.items():
            self.fig.add_trace(
                        go.Scatter(
                            name="muon site #"+label,
                            x = self.t_axes,
                            y = data,
                            mode='lines',
                            marker=dict(
                                 size=10), 
                            line=dict(
                                 width=2),

                        ),
                    )
        #updating the layout.
        ## we stack the bar plots, for each muon site/tick (self.muon_labels)
        self.fig.update_layout(
            clickmode='event+select',
            title='Kubo-Toyabe polarization',
            barmode='group',
            yaxis=dict(title='P<sup>KT</sup>(T)'),
            xaxis=dict(title='time (μs)'),
            legend=dict(x=0.01, y=1, xanchor='left', yanchor='top'),
            width=600, # Width of the plot
            height=500, # Height of the plot

            font=dict( # Font size and color of the labels
                size=12,
                color='#333333',
            ),
            plot_bgcolor='gainsboro', # Background color of the plot
            #paper_bgcolor='white', # Background color of the paper

            #bargap=0.000001, # Gap between bars
            #bargroupgap=0.4, # Gap between bar groups
        )
        
        super().__init__(children=[self.fig],**kwargs)
        
class MuonSummaryBarPlotWidget(ipw.VBox):
    """
    Widget for the summary bar plot with all unique muon sites.
    
    Inputs:
    df: the pandas dataframe with all the collected results
    selected: the index of the selected muon site, to enhance the corresponding tick in the plot. 
              it will be connected to the structureviewer and the dropdown.
    """
    
    #needed to be observed.
    selected = traitlets.Instance(str, allow_none=True)
    
    def __init__(
        self,
        df,
        selected=None,  
        **kwargs):
        
        self.fig = go.FigureWidget()
        self.df=df
        self.selected = selected
        self.muon_indexes = self.df.loc["muon_index"].tolist()
        self.muon_labels = self.generate_labels()

        #figure widget
        ## the scatter plots.
        for entry in ["delta_E","B_T_norm"]:
            if entry in self.df.index.tolist():
                label = change_names_for_html[entry]
                yaxis = 'y2' if entry=="delta_E" else 'y'
                color = "mediumslateblue" if entry=="delta_E" else 'blue'
                symbol = "circle" if entry=="delta_E" else "square"

                self.fig.add_trace(
                        go.Scatter(
                            name=label,
                            x = self.muon_labels,
                            y = self.df.loc[entry].tolist(),
                            mode='markers',
                            marker=dict(
                                color=color, size=10, symbol=symbol), 
                            line=dict(
                                color=color, width=2),
                            yaxis=yaxis,

                        ),
                    )
            
        ## the bar plots.    
        for entry in ["Bdip_norm","hyperfine_norm"]:
            if entry in self.df.index.tolist():
                label = change_names_for_html[entry]

                self.fig.add_trace(
                    go.Bar(
                        name=label,
                        x = self.muon_labels,
                        y = self.df.loc[entry].tolist(),
                        marker=dict(
                        color="lightcoral" if entry == "Bdip_norm" else "darkseagreen",
                        ),
                        marker_line_width=0.5,
                    ),
                )
    
    
        #updating the layout.
        ## we stack the bar plots, for each muon site/tick (self.muon_labels)
        self.fig.update_layout(
            #title='Summary',
            barmode='group',
            yaxis=dict(title='Field magnitude (T)'),
            yaxis2=dict(title='ΔE<sub>total</sub> (eV)',
            titlefont=dict(color='mediumslateblue'),
            tickfont=dict(color='mediumslateblue'),
            overlaying='y',
            side='right'),
            legend=dict(x=0.01, y=1, xanchor='left', yanchor='top'),
            #width=400, # Width of the plot
            #height=500, # Height of the plot

            font=dict( # Font size and color of the labels
                size=12,
                color='#333333',
            ),
            plot_bgcolor='gainsboro', # Background color of the plot
            #paper_bgcolor='white', # Background color of the paper

            #bargap=0.000001, # Gap between bars
            #bargroupgap=0.4, # Gap between bar groups
        )
        
        
        self.observe(self._observe_selected,"selected")
        
        super().__init__(children=[self.fig],**kwargs)
    
    def generate_labels(self,):
        # here we update the ticks, so that we enhance the selected muon (picked in the structure or dropdown).
        muon_labels = []
        clicked_muon = self.selected
        for ind in self.muon_indexes:
            if clicked_muon == ind:
                muon_labels.append(f"<b>Selected: muon #{ind}<b>")
            else:
                muon_labels.append(f"muon site #{ind}")
        
        return muon_labels
    
    def _observe_selected(self, change):
        #if the selected value changes, we update labels for each trace, 
        #or better we update the x values of each trace.
        self.muon_labels = self.generate_labels()
        for trace in self.fig.data:
            #each time we add a trace in the init method, we add an element in the self.fig.data tuple.
            trace.x = self.muon_labels
            
            
class MuonSummaryTableWidget(ipw.VBox):
    
    reduced_html_converter = {
        "muon_index": "muon #",
        "delta_E":"ΔE<sub>total</sub> (eV)",
        
        "B_T_norm":"|B<sub>total</sub>| (T)",
        "Bdip_norm":"|B<sub>dip</sub>| (T)",
        "hyperfine_norm":"|B<sub>hyperfine</sub>| (T)",
        
        }
    
    def __init__(self,df,**kwargs):
        import copy
        
        self.df = df
        
        self.curated_reduced_html_converter = {        
        }
        
        
        for k in self.df.index:
            if k in self.reduced_html_converter.keys():
                self.curated_reduced_html_converter[k] = self.reduced_html_converter[k]
        
        table_html = self._generate_html_table()
        self.table_widget = ipw.VBox([ipw.HTML(value="<b>Summary for all the unique muon sites, sorted by energy:</b>"),
                                      ipw.HTML(value=table_html)])
        
        super().__init__(children=[self.table_widget],**kwargs)
        
    def _generate_html_table(self):
        #headers
        table_html = '<table style="width:100%">'
        table_html += "<tr>"
        for k,v in self.reduced_html_converter.items():
            if k in self.df.index.to_list(): # may not contain magnetic info
                table_html += f"<td style='text-align:center;'> <b>{v}</b> </td>"
        table_html += "</tr>"

        #Here the data for each muon index.
        for k in self.df.columns.to_list(): # may not contain magnetic info
            table_html += "<tr>"
            #table_html += "<td style='text-align:center;'>{}</td>".format(v)
            for kk,v in self.reduced_html_converter.items():
                if kk in self.df[k].index.tolist():
                    value = self.df[k].loc[kk]
                    if not isinstance(value,str):
                        table_html += "<td style='text-align:center;'>{}</td>".format(np.round(float(value),3))
                    else: #the muon index is s string.
                        table_html += "<td style='text-align:center;'>{}</td>".format(value)
            table_html += "</tr>"
        table_html += "</table>"
        
        payload = base64.b64encode(self.df.loc[self.curated_reduced_html_converter.keys()].to_csv(index=True).encode()).decode()
        fname = f"muon_short_summary.csv"
        table_html += f"""Download this table in csv format: <a download="{fname}"
        href="data:text/csv;base64,{payload}" target="_blank">{fname}</a><br>"""
        
        payload = base64.b64encode(self.df.to_csv(index=True).encode()).decode()
        fname = f"muon_detailed_summary.csv"
        table_html += f"""Download a complete summary in csv format: <a download="{fname}"
        href="data:text/csv;base64,{payload}" target="_blank">{fname}</a>"""

        return table_html
    
    
class SummaryMuonStructureBarWidget(ipw.VBox):
        
    def __init__(self, structure=None, df=None, selected=None,tags=None,**kwargs):
        """
        structure is the unit cell with all the muon sites.
        """
        
        self.df = df
        self.structure = structure
        self.tags = tags
        
        self.muon_index_list = df.columns.tolist()
        self.muon_index_list.sort()
        
        if len(self.df)>0: 
            """
            Structure of the widget:
            
            structureviewer/picker
            barplot+Vbox[table,dropdown]
            """
            self.cell_label = ipw.HTML("Unit cell containing all the unique muon sites:")
            self.child1=StructureDataViewer(structure=self.structure)
            self.child1.observe(self._update_picked, names='displayed_selection')
            #in an HBox:
            self.child2=MuonSummaryBarPlotWidget(self.df)
            self.child3=MuonSummaryTableWidget(self.df,)
            
            self.dropdown = ipw.Dropdown(
                options=[None]+self.muon_index_list,
                value=None,

            )
            self.dropdown.observe(self._update_selected, names='value')
            self.dropdown_label = ipw.HTML("Select muon site:")
            self.dropdown_widget = ipw.HBox(children=[self.dropdown_label,self.dropdown])
            
            self.KT_asymmetry = KT_asymmetry_widget(df)
            
            children = [self.dropdown_widget,
                        self.cell_label,
                        self.child1,
                        ipw.HBox([self.child3,
                                    self.child2,
                                ]),
                       self.KT_asymmetry
                       ]
        else:
            children = []
            
        super().__init__(children, **kwargs)
        
    def _update_selected(self,change):
        #This is triggered changing the dropdown selection.
        if not change.new: 
            #we selected None, so we reset the selection.
            self.child1.displayed_selection = []
            self.child2.selected = None
        else:
            self.child2.selected = change["new"]
            if self.tags.index(change["new"]):
                #this gives angle errors ==>self.child1.displayed_selection.append(self.tags.index(change["new"]))
                self.child1.displayed_selection = [self.tags.index(change["new"])]
                
    def _update_picked(self,change):
        #This is triggered changing the picked atom selected in the structure view.
        if len(change["new"])>0:
            if change["new"][-1] <= len(self.tags): #temporary fixing for supercells generate live in structuredataviewer: the indexes increases 
                if self.tags[change["new"][-1]]:
                    self.child2.selected = str(self.tags[change["new"][-1]])
                    self.dropdown.value = self.child2.selected         
        else:
            self.child2.selected = None         

###############end summary muon sites widgets #####################################
