import unittest
import sys
sys.path.append("/opt/stack/tempest/tempest/api/workloadmgr/cli_automation")
from config import configuration,command_argument_string
from utils import cli_parser,query_data

class snapshot_list_command_test(unittest.TestCase):
    def runTest(self):
        rc = cli_parser.cli_returncode(command_argument_string.snapshot_list)
        print rc
        if rc != 0:
            raise Exception("Command did not execute correctly!!!")
        else:
            print ("Command executed correctly!!!")
        wc = query_data.get_available_snapshots(configuration.snapshot_name)
	print wc
        out = cli_parser.cli_output(command_argument_string.snapshot_list)
	print out
        if (int(wc) == int(out)):
            print "Snapshot list command listed available snapshots correctly"
        else:
            raise Exception ("Snapshot list command did not list available snapshots correctly!!!")



if __name__ == '__main__':
    unittest.main()




