import json
import os
import sys
import time
import paramiko

import yaml
from oslo_log import log as logging

from tempest import command_argument_string
from tempest import config
from tempest import reporting
from tempest.api.workloadmgr import base
from tempest import tvaultconf
from tempest.lib import decorators
from tempest.util import cli_parser
from tempest.util import query_data

sys.path.append(os.getcwd())

LOG = logging.getLogger(__name__)
CONF = config.CONF


class WorkloadTest(base.BaseWorkloadmgrTest):
    credentials = ['primary']

    @classmethod
    def setup_clients(cls):
        super(WorkloadTest, cls).setup_clients()

    def assign_floating_ips(self, fip, vm_id, cleanup):
        self.set_floating_ip(str(fip), vm_id, floatingip_cleanup=cleanup)
        return fip

    def create_directory_on_remote_machine(self, ssh, data_dir_path):
        cmd = "sudo mkdir -p " + data_dir_path
        LOG.debug("CMD TO RUN = "+ str(cmd))
        stdin, stdout, stderr = ssh.exec_command(cmd)
        time.sleep(10)

    def data_ops_for_bootdisk(self, flo_ip, data_dir_path, file_count):
        ssh = self.SshRemoteMachineConnectionWithRSAKey(str(flo_ip))
        self.install_qemu(ssh)
        self.create_directory_on_remote_machine(ssh, data_dir_path)
        self.addCustomfilesOnLinuxVM(ssh, data_dir_path, file_count)
        ssh.close()

    def create_snapshot(self, workload_id, is_full=True):
        if is_full:
            substitution = 'Full'
        else:
            substitution = 'Incremental'

        snapshot_id, command_execution, snapshot_execution = self.workload_snapshot_cli(
            workload_id, is_full=is_full)
        if command_execution == 'pass':
            reporting.add_test_step("{} snapshot command execution".format(
                substitution), tvaultconf.PASS)
            LOG.debug("Command executed correctly for full snapshot")
        else:
            LOG.debug("{} snapshot command execution failed.".format(str(substitution)))
            raise Exception(
                "Command did not execute correctly for full snapshot")

        if snapshot_execution == 'pass':
            reporting.add_test_step("{} snapshot".format(
                substitution), tvaultconf.PASS)
        else:
            LOG.debug("{} snapshot failed".format(str(substitution)))
            raise Exception("Full snapshot failed")
        return(snapshot_id)

    @decorators.attr(type='workloadmgr_cli')
    def test_restore_with_blank_name(self):
        try:
            deleted = 0
            data_dir_path = ["/opt/testfolder1", "/opt/testfolder2"]
            global volumes
            ## VM and Workload ###
            tests = [['tempest.api.workloadmgr.restore.test_inplace_restore_with_blank_name',
                      0],
                     ['tempest.api.workloadmgr.restore.test_oneclick_restore_with_blank_name',
                      0]]


            fip = self.get_floating_ips()
            if len(fip) < 2:
                raise Exception("Floating ips unavailable")

            # create key_pair value
            kp = self.create_key_pair(
                tvaultconf.key_pair_name, keypair_cleanup=True)
            LOG.debug("Key_pair : " + str(kp))

            # create vm
            vm_id = self.create_vm(key_pair=kp, vm_cleanup=True)
            LOG.debug("VM ID : " + str(vm_id))
            time.sleep(30)

            # assign floating ip
            floating_ip_1 = self.assign_floating_ips(fip[0], vm_id, False)
            LOG.debug("Assigned floating IP : " + str(floating_ip_1))
            time.sleep(20)

            # add some data to boot disk...
            self.data_ops_for_bootdisk(floating_ip_1, data_dir_path[0], 3)

            # Create workload using CLI
            workload_create = command_argument_string.workload_create + \
                              " --instance instance-id=" + str(vm_id)

            rc = cli_parser.cli_returncode(workload_create)

            if rc != 0:
                LOG.debug("Execute workload-create command using cli")
                raise Exception(
                    "Execute workload-create command using cli")
            else:
                reporting.add_test_step(
                    "Execute workload-create command using cli",
                    tvaultconf.PASS)

            time.sleep(10)

            # check workload status
            wid = query_data.get_workload_id_in_creation(tvaultconf.workload_name)
            LOG.debug("Workload ID: " + str(wid))
            if (wid is not None):
                self.wait_for_workload_tobe_available(wid)
                if (self.getWorkloadStatus(wid) == "available"):
                    LOG.debug("Create workload using cli passed.")
                    reporting.add_test_step(
                        "Create workload using cli", tvaultconf.PASS)
                else:
                    LOG.debug("Create workload using cli failed.")
                    raise Exception("Create workload using cli")
            else:
                LOG.debug("Create workload using cli failed.")
                raise Exception("Create workload using cli")

            # take full snapshot
            snapshot_id = self.create_snapshot(wid, is_full=True)

            # Add some more data to files on VM
            self.data_ops_for_bootdisk(floating_ip_1, data_dir_path[1], 3)

            ### Incremental snapshot ###
            incr_snapshot_id = self.create_snapshot(wid, is_full=False)


            self.wait_for_workload_tobe_available(wid)
            snapshot_status = self.getSnapshotStatus(wid, snapshot_id)

            if (snapshot_status == "available"):
                LOG.debug("Full snapshot created.")
                reporting.add_test_step("Create full snapshot", tvaultconf.PASS)
            else:
                LOG.debug("Full snapshot creation failed.")
                raise Exception("Create full snapshot")

            reporting.test_case_to_write()

            ### In-place restore ###
            reporting.add_test_script(tests[0][0])

            volumeslist = []
            rest_details = {}
            rest_details['rest_type'] = 'inplace'
            rest_details['instances'] = {vm_id: volumeslist}

            payload = self.create_restore_json(rest_details)
            restore_json = json.dumps(payload)
            LOG.debug("restore.json for inplace restore: " + str(restore_json))
            # Create Restore.json
            with open(tvaultconf.restore_filename, 'w') as f:
                f.write(str(yaml.safe_load(restore_json)))

            # Create in-place restore with CLI command
            restore_command = command_argument_string.inplace_restore_with_blank_name + \
                              str(tvaultconf.restore_filename) + " " + str(snapshot_id)
            LOG.debug("Inplace Restore_command is :=" + str(restore_command))

            rc = cli_parser.cli_returncode(restore_command)
            
            if rc != 0:
                LOG.debug("In-Place restore cli command with blank name command")
                raise Exception("In-Place restore cli command with blank name command")
            else:
                reporting.add_test_step(
                    "In-Place restore cli command with blank name command", tvaultconf.PASS)
                LOG.debug("In-Place restore cli command with blank name executed correctly")


            # get restore id from database
            restore_id_1 = query_data.get_snapshot_restore_id(snapshot_id)


            self.wait_for_snapshot_tobe_available(wid, snapshot_id)

            # get in-place restore status
            if (self.getRestoreStatus(wid, snapshot_id, restore_id_1) == "available"):
                reporting.add_test_step("In-place restore of full snapshot", tvaultconf.PASS)
                reporting.set_test_script_status(tvaultconf.PASS)
                tests[0][1] = 1

            else:
                LOG.debug("In-place restore of full snapshot")
                raise Exception("In-place restore of full snapshot")

            # Fetch instance details after restore
            inplace_vm_list = []
            inplace_vm_list = self.get_restored_vm_list(restore_id_1)
            LOG.debug("Restored vm(In-place) ID : " + str(inplace_vm_list))

            reporting.test_case_to_write()

            ### One-click restore ###
            reporting.add_test_script(tests[1][0])

            # Delete the original instance
            self.delete_vm(vm_id)
            LOG.debug(
                "Instance deleted successfully for one click restore : " +
                str(vm_id))

            deleted = 1
            time.sleep(10)

	        # Create one-click restore using CLI command
            restore_command = command_argument_string.oneclick_restore_with_blank_name + str(incr_snapshot_id)
            LOG.debug("Restore_command is :=" + str(restore_command))

            rc = cli_parser.cli_returncode(restore_command)
            if rc != 0:
                LOG.debug("One-click restore cli with blank name command failed to execute")
                raise Exception("One-click restore cli with blank name command")
            else:
                reporting.add_test_step(
                    "One-click-restore cli with blank name command",
                    tvaultconf.PASS)
                LOG.debug("One-click restore with blank name command executed successfully")

            restore_id_2 = query_data.get_snapshot_restore_id(incr_snapshot_id)

            self.wait_for_snapshot_tobe_available(
                wid, incr_snapshot_id)

            # get one-click restore status
            if (self.getRestoreStatus(wid, incr_snapshot_id, restore_id_2) == "available"):
                LOG.debug("One-click restore of full snapshot passed.")
                reporting.add_test_step("One-click restore of full snapshot", tvaultconf.PASS)
                reporting.set_test_script_status(tvaultconf.PASS)
                tests[1][1] = 1
            else:
                LOG.debug("One-click restore of full snapshot failed.")
                raise Exception("One-click restore of full snapshot")

            # Fetch instance details after restore
            oneclick_vm_list = []
            oneclick_vm_list = self.get_restored_vm_list(restore_id_1)
            LOG.debug("Restored vms list: " + str(oneclick_vm_list))

            reporting.test_case_to_write()

        except Exception as e:
            LOG.error("Exception: " + str(e))
            reporting.add_test_step(str(e), tvaultconf.FAIL)
            reporting.set_test_script_status(tvaultconf.FAIL)

        finally:
            for test in tests:
                if test[1] != 1:
                    reporting.add_test_script(test[0])
                    reporting.set_test_script_status(tvaultconf.FAIL)
                    reporting.test_case_to_write()

            try:
                if (deleted == 0):
                    self.delete_vm(vm_id)

                self.delete_vm(oneclick_vm_list[0])
                self.delete_vm(inplace_vm_list[0])
            except BaseException:
                pass




