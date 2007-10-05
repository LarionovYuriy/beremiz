import os, sys
base_folder = os.path.split(sys.path[0])[0]
CanFestivalPath = os.path.join(base_folder, "CanFestival-3")
sys.path.append(os.path.join(CanFestivalPath, "objdictgen"))

from nodelist import NodeList
from nodemanager import NodeManager
import config_utils, gen_cfile
from networkedit import networkedit
import canfestival_config

class _NetworkEdit(networkedit):
    " Overload some of CanFestival Network Editor methods "
    def OnCloseFrame(self, event):
        " Do reset _NodeListPlug.View when closed"
        self._onclose()
        event.Skip()

class _NodeListPlug(NodeList):
    XSD = """<?xml version="1.0" encoding="ISO-8859-1" ?>
    <xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">
      <xsd:element name="CanFestivalNode">
        <xsd:complexType>
          <xsd:attribute name="CAN_Device" type="xsd:string" use="required" />
          <xsd:attribute name="CAN_Baudrate" type="xsd:string" use="required" />
          <xsd:attribute name="NodeId" type="xsd:string" use="required" />
          <xsd:attribute name="Sync_TPDOs" type="xsd:boolean" use="required" default="true"/>
        </xsd:complexType>
      </xsd:element>
    </xsd:schema>
    """

    def __init__(self):
        manager = NodeManager()
        # TODO change netname when name change
        NodeList.__init__(self, manager, self.BaseParams.getName())
        self.LoadProject(self.PlugPath())

    _View = None
    def _OpenView(self, logger):
        if not self._View:
            def _onclose():
                self._View = None
            def _onsave():
                self.GetPlugRoot().SaveProject()
            self._View = _NetworkEdit(self.GetPlugRoot().AppFrame, self)
            # TODO redefine BusId when IEC channel change
            self._View.SetBusId(self.GetCurrentLocation())
            self._View._onclose = _onclose
            self._View._onsave = _onsave
            self._View.Show()

    PluginMethods = [("NetworkEdit",_OpenView)]

    def OnPlugClose(self):
        if self._View:
            self._View.Close()

    def PlugTestModified(self):
        return self.HasChanged()
        
    def OnPlugSave(self):
        self.SetRoot(self.PlugPath())
        self.SaveProject()
        return True

    def PlugGenerate_C(self, buildpath, locations, logger):
        """
        Generate C code
        @param current_location: Tupple containing plugin IEC location : %I0.0.4.5 => (0,0,4,5)
        @param locations: List of complete variables locations \
            [{"IEC_TYPE" : the IEC type (i.e. "INT", "STRING", ...)
            "NAME" : name of the variable (generally "__IW0_1_2" style)
            "DIR" : direction "Q","I" or "M"
            "SIZE" : size "X", "B", "W", "D", "L"
            "LOC" : tuple of interger for IEC location (0,1,2,...)
            }, ...]
        @return: [(C_file_name, CFLAGS),...] , LDFLAGS_TO_APPEND
        """
        current_location = self.GetCurrentLocation()
        # define a unique name for the generated C file
        prefix = "_".join(map(lambda x:str(x), current_location))
        Gen_OD_path = os.path.join(buildpath, "OD_%s.c"%prefix )
        # Create a new copy of the model with DCF loaded with PDO mappings for desired location
        master = config_utils.GenerateConciseDCF(locations, current_location, self, self.CanFestivalNode.getSync_TPDOs(),"OD_%s"%prefix)
        res = gen_cfile.GenerateFile(Gen_OD_path, master)
        if res :
            raise Exception, res
        
        return [(Gen_OD_path,canfestival_config.getCFLAGS(CanFestivalPath))],"",False
    
class RootClass:
    XSD = """<?xml version="1.0" encoding="ISO-8859-1" ?>
    <xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">
      <xsd:element name="CanFestivalInstance">
        <xsd:complexType>
          <xsd:attribute name="CAN_Driver" type="xsd:string" use="required" />
        </xsd:complexType>
      </xsd:element>
    </xsd:schema>
    """

    PlugChildsTypes = [("CanOpenNode",_NodeListPlug)]
    
    def PlugGenerate_C(self, buildpath, locations, logger):
        
        format_dict = {"locstr" : "_".join(map(str,self.GetCurrentLocation())),
                       "candriver" : self.CanFestivalInstance.getCAN_Driver(),
                       "nodes_includes" : "",
                       "board_decls" : "",
                       "nodes_declare" : "",
                       "nodes_init" : "",
                       "nodes_open" : "",
                       "nodes_close" : "",
                       "nodes_send_sync" : "",
                       "nodes_proceed_sync" : ""}
        for child in self.IECSortedChilds():
            childlocstr = "_".join(map(str,child.GetCurrentLocation()))
            nodename = "OD_%s" % childlocstr

            format_dict["nodes_includes"] += '#include "%s.h"\n'%(nodename)
            format_dict["board_decls"] += 'BOARD_DECL(%s, "%s", "%s")\n'%(
                   nodename,
                   child.CanFestivalNode.getCAN_Device(),
                   child.CanFestivalNode.getCAN_Baudrate())
            format_dict["nodes_declare"] += 'NODE_DECLARE(%s, %s)\n    '%(
                   nodename,
                   child.CanFestivalNode.getNodeId())
            format_dict["nodes_init"] += 'NODE_INIT(%s, %s)\n    '%(
                   nodename,
                   child.CanFestivalNode.getNodeId())
            format_dict["nodes_open"] += 'NODE_OPEN(%s)\n    '%(nodename)
            format_dict["nodes_close"] += 'NODE_CLOSE(%s)\n    '%(nodename)
            format_dict["nodes_send_sync"] += 'NODE_SEND_SYNC(%s)\n    '%(nodename)
            format_dict["nodes_proceed_sync"] += 'NODE_PROCEED_SYNC(%s)\n    '%(nodename)
        filename = os.path.join(os.path.split(__file__)[0],"cf_runtime.c")
        cf_main = open(filename).read() % format_dict
        cf_main_path = os.path.join(buildpath, "CF_%(locstr)s.c"%format_dict)
        f = open(cf_main_path,'w')
        f.write(cf_main)
        f.close()
        
        return [(cf_main_path, canfestival_config.getCFLAGS(CanFestivalPath))],canfestival_config.getLDFLAGS(CanFestivalPath), True

