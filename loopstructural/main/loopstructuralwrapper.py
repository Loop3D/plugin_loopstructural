from typing import List

import numpy as np
import pandas as pd
from LoopStructural import GeologicalModel
from LoopStructural.modelling.input import ProcessInputData

from .vectorLayerWrapper import qgsLayerToDataFrame


class QgsProcessInputData(ProcessInputData):
    def __init__(
        self,
        basal_contacts,
        groups: List[dict],
        fault_trace,
        fault_properties,
        structural_data,
        dtm,
        columnmap: dict,
        roi,
        top: float,
        bottom: float,
        dip_direction: bool,
        rotation,
        faultNetwork: np.ndarray = None,
        faultStratigraphy: np.ndarray = None,
        faultlist: List[str] = None,
    ):
        i, j = np.where(faultNetwork == 1)
        edges = []
        edgeproperties = []
        for ii, jj in zip(i, j):
            edges.append((faultlist[jj], faultlist[ii]))
            edgeproperties.append({'type': 'abuts'})

        contact_locations = qgsLayerToDataFrame(basal_contacts, dtm)
        fault_data = qgsLayerToDataFrame(fault_trace, dtm)
        contact_orientations = qgsLayerToDataFrame(structural_data, dtm)
        thicknesses = {}
        stratigraphic_order = []
        colours = {}
        for g in groups:
            stratigraphic_order.append((g['name'], [u['name'] for u in g['units']]))
            for u in g['units']:
                thicknesses[u['name']] = u['thickness']
                colours[u['name']] = u['colour']
        # for key in stratigraphic_column.keys():
        #     thicknesses[key] = stratigraphic_column[key]['thickness']
        # stratigraphic_order = [None] * len(thicknesses)
        # for key in stratigraphic_column.keys():
        #     stratigraphic_order[stratigraphic_column[key]['order']] = key
        # print(stratigraphic_column)
        # stratigraphic_order = [('sg', stratigraphic_order)]
        roi_rectangle = roi.extent()
        minx = roi_rectangle.xMinimum()
        maxx = roi_rectangle.xMaximum()
        miny = roi_rectangle.yMinimum()
        maxy = roi_rectangle.yMaximum()
        # transformer = EuclideanTransformation(minx,miny,rotation)

        origin = (minx, miny, bottom)
        maximum = (maxx, maxy, top)
        if contact_locations is not None and columnmap['unitname'] in contact_locations:
            contact_locations = contact_locations.rename(columns={columnmap['unitname']: 'name'})[
                ['X', 'Y', 'Z', 'name']
            ]
        else:
            contact_locations = None
        if fault_data is not None and columnmap['faultname'] in fault_data:
            fault_data = fault_data.rename(columns={columnmap['faultname']: 'fault_name'})[
                ['X', 'Y', 'Z', 'fault_name']
            ]
            if np.all(fault_data['fault_name'].isna()):
                raise ValueError('Fault column name is all None. Check the column name')
        else:
            fault_data = None

        if (
            contact_orientations is not None
            and columnmap['structure_unitname'] in contact_orientations
            and columnmap['dip'] in contact_orientations
            and columnmap['orientation'] in contact_orientations
        ):
            contact_orientations = contact_orientations.rename(
                columns={
                    columnmap['structure_unitname']: 'name',
                    columnmap['dip']: 'dip',
                    columnmap['orientation']: 'strike',
                }
            )[['X', 'Y', 'Z', 'dip', 'strike', 'name']]
            contact_orientations['dip'] = contact_orientations['dip'].astype(float)
            contact_orientations['strike'] = contact_orientations['strike'].astype(float)
            if np.all(contact_orientations['name'].isna()):
                raise ValueError('Unit column name is all None. Check the column name')
            if np.all(contact_orientations['dip'].isna()):
                raise ValueError('Dip column name is all None. Check the column name')
            if np.all(contact_orientations['strike'].isna()):
                raise ValueError('Strike column name is all None. Check the column name')
            if dip_direction:
                contact_orientations['strike'] = contact_orientations['strike'] - 90
        else:
            contact_orientations = None
        faults = []
        for fault_name in fault_properties.keys():
            fault = fault_properties[fault_name]
            if fault['active']:
                faults.append(
                    {
                        'fault_name': fault_name,
                        'fault_dip': fault['fault_dip'],
                        'displacement': fault['displacement'],
                        'major_axis': fault['major_axis'],
                        'intermediate_axis': fault['intermediate_axis'],
                        'minor_axis': fault['minor_axis'],
                        'centreEasting': fault['fault_centre']['x'],
                        'centreNorthing': fault['fault_centre']['y'],
                        'centreElevation': 0,  # if fault['centre']fault['centre'].z(),
                        'fault_pitch': fault['fault_pitch'],
                        # 'active': fault['active'],
                        # 'azimuth': fault['azimuth'],
                        # 'crs': fault['crs'],
                    }
                )
        fault_properties = None
        if len(faults) > 0:

            fault_properties = pd.DataFrame(faults)
            fault_properties['fault_name'] = fault_properties['fault_name'].astype(str)
            fault_properties = fault_properties.set_index('fault_name')
            fault_data['fault_name'] = fault_data['fault_name'].astype(str)
        super().__init__(
            contacts=contact_locations,
            stratigraphic_order=stratigraphic_order,
            thicknesses=thicknesses,
            fault_locations=fault_data,
            contact_orientations=contact_orientations,
            fault_orientations=None,
            fault_properties=fault_properties,
            origin=origin,
            maximum=maximum,
            fault_edges=edges if len(edges) > 0 else None,
            fault_edge_properties=edgeproperties if len(edgeproperties) > 0 else None,
            colours=colours,
            # fault_edges=[(fault,None) for fault in fault_data['fault_name'].unique()],
        )

    def get_model(self):
        return GeologicalModel.from_processor(self)
