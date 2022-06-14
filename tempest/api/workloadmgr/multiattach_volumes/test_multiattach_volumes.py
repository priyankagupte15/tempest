from tempest.api.workloadmgr import base
from tempest import config
from tempest.lib import decorators
from tempest import test
import time
from oslo_log import log as logging
from tempest import tvaultconf
from tempest import reporting
from tempest import command_argument_string
from tempest.util import cli_parser

LOG = logging.getLogger(__name__)
CONF = config.CONF


class WorkloadsTest(base.BaseWorkloadmgrTest):
    credentials = ['primary']
    workload_id = ""
    vm_id = ""
    volume_id = ""
    policy_id = ""
    secret_uuid = ""
    exception = ""

    @classmethod
    def setup_clients(cls):
        super(WorkloadsTest, cls).setup_clients()

    def _set_frm_user(self):
        self.frm_image = list(CONF.compute.fvm_image_ref.keys())[0]
        self.frm_ssh_user = ""
        if "centos" in self.frm_image:
            self.frm_ssh_user = "centos"
        elif "ubuntu" in self.frm_image:
            self.frm_ssh_user = "ubuntu"

    def _add_data_on_instance_and_volume(self, ip, full=True):
        ssh = self.SshRemoteMachineConnectionWithRSAKey(ip)
        file_count = 5
        if full:
            self.install_qemu(ssh)
            self.execute_command_disk_create(ssh, str(ip),
                                         [tvaultconf.volumes_parts[0]], [tvaultconf.mount_points[0]])
            self.execute_command_disk_mount(ssh, str(ip),
                                        [tvaultconf.volumes_parts[0]], [tvaultconf.mount_points[0]])
            file_count = 3

        self.addCustomfilesOnLinuxVM(ssh, "/opt", file_count)
        self.addCustomfilesOnLinuxVM(ssh, tvaultconf.mount_points[0], file_count)
        md5sums_opt = self.calculatemmd5checksum(ssh, "/opt")
        md5sums_vol = self.calculatemmd5checksum(ssh, tvaultconf.mount_points[0])
        ssh.close()
        return md5sums_opt, md5sums_vol

    def _selective_restore(self,payload,ip_list,md5sums_list,full=True):
        if full:
            snapshot_id = self.snapshot_id
            snapshot_type = 'full'
        else:
            snapshot_id = self.snapshot_id2
            snapshot_type = 'incremental'
        # Trigger selective restore of full snapshot
        restore_id_1 = self.snapshot_selective_restore(
            self.wid, snapshot_id,
            restore_name="selective_restore_full_snap",
            instance_details=payload['instance_details'],
            network_details=payload['network_details'])
        self.wait_for_snapshot_tobe_available(self.wid, self.snapshot_id)
        if (self.getRestoreStatus(self.wid, self.snapshot_id,
                                  restore_id_1) == "available"):
            reporting.add_test_step("Selective restore of " + snapshot_type + " snapshot",
                                    tvaultconf.PASS)
            vm_list = self.get_restored_vm_list(restore_id_1)
            LOG.debug("Restored vm(selective) ID : " + str(vm_list))
            time.sleep(60)
            self.set_floating_ip(ip_list[0], vm_list[0])
            self.set_floating_ip(ip_list[1], vm_list[1])
            LOG.debug("Floating ip assigned to selective restored vm -> " + \
                      f"{ip_list[0]} and {ip_list[1]}")
            ssh = self.SshRemoteMachineConnectionWithRSAKey(ip_list[0])
            self.execute_command_disk_mount(ssh, ip_list[0],
                                            [tvaultconf.volumes_parts[0]], [tvaultconf.mount_points[0]])
            md5sums_after_opt_selective1 = self.calculatemmd5checksum(ssh, "/opt")
            md5sums_after_vol_selective1 = self.calculatemmd5checksum(ssh, tvaultconf.mount_points[0])
            LOG.debug(
                f"md5sums_after_selective_opt: {md5sums_after_opt_selective1} md5sums_after_selective_vol: {md5sums_after_vol_selective1}")
            ssh.close()

            ssh = self.SshRemoteMachineConnectionWithRSAKey(ip_list[1])
            self.execute_command_disk_mount(ssh, ip_list[1],
                                            [tvaultconf.volumes_parts[0]], [tvaultconf.mount_points[0]])
            md5sums_after_opt_selective2 = self.calculatemmd5checksum(ssh, "/opt")
            md5sums_after_vol_selective2 = self.calculatemmd5checksum(ssh, tvaultconf.mount_points[0])
            LOG.debug(
                f"md5sums_after_selective_opt: {md5sums_after_opt_selective2} md5sums_after_selective_vol: {md5sums_after_vol_selective2}")
            ssh.close()

            if md5sums_list[0] in [md5sums_after_opt_selective1,md5sums_after_opt_selective2]:
                LOG.debug("***MDSUMS MATCH***")
                reporting.add_test_step(
                    "Md5 Verification for boot disk for VM1", tvaultconf.PASS)
            else:
                LOG.debug("***MDSUMS DON'T MATCH*** expected: " + md5sums_list[0] + " actual: " + str([md5sums_after_opt_selective1,md5sums_after_opt_selective2]))
                reporting.add_test_step(
                    "Md5 Verification for boot disk for VM1", tvaultconf.FAIL)
                reporting.set_test_script_status(tvaultconf.FAIL)

            if md5sums_list[1] in [md5sums_after_vol_selective1,md5sums_after_vol_selective2]:
                LOG.debug("***MDSUMS MATCH***")
                reporting.add_test_step(
                    "Md5 Verification for volume disk for VM1", tvaultconf.PASS)
            else:
                LOG.debug("***MDSUMS DON'T MATCH*** expected: " + md5sums_list[1] + " actual: " + str([md5sums_after_vol_selective1,md5sums_after_vol_selective2]))
                reporting.add_test_step(
                    "Md5 Verification for volume disk for VM1", tvaultconf.FAIL)
                reporting.set_test_script_status(tvaultconf.FAIL)

            if md5sums_list[2] in [md5sums_after_opt_selective2,md5sums_after_opt_selective1]:
                LOG.debug("***MDSUMS MATCH***")
                reporting.add_test_step(
                    "Md5 Verification for boot disk for VM2", tvaultconf.PASS)
            else:
                LOG.debug("***MDSUMS DON'T MATCH*** expected: " + md5sums_list[2] + " actual: " + str([md5sums_after_vol_selective1,md5sums_after_vol_selective2]))
                reporting.add_test_step(
                    "Md5 Verification for boot disk for VM2", tvaultconf.FAIL)
                reporting.set_test_script_status(tvaultconf.FAIL)

            if md5sums_list[3] in [md5sums_after_vol_selective2,md5sums_after_vol_selective1]:
                LOG.debug("***MDSUMS MATCH***")
                reporting.add_test_step(
                    "Md5 Verification for volume disk for VM2", tvaultconf.PASS)
            else:
                LOG.debug("***MDSUMS DON'T MATCH*** expected: " + md5sums_list[3] + " actual: " + str([md5sums_after_vol_selective2,md5sums_after_vol_selective1]))
                reporting.add_test_step(
                    "Md5 Verification for volume disk for VM2", tvaultconf.FAIL)
                reporting.set_test_script_status(tvaultconf.FAIL)

        else:
            reporting.add_test_step("Selective restore of " + snapshot_type + " snapshot",
                                    tvaultconf.FAIL)

    @decorators.attr(type='workloadmgr_api')
    def test_01_multiattach_volumes(self):
        try:
            test_var = "tempest.api.workloadmgr.multiattach_volumes.test_image_booted_"
            tests = [[test_var + "workload_api", 0],
                     [test_var + "full_snapshot_api", 0],
                     [test_var + "incremental_snapshot_api", 0],
                     # [test_var+"snapshot_mount_api", 0],
                     # [test_var+"filesearch_api", 0],
                     [test_var + "selectiverestore_api", 0],
                     [test_var+"inplacerestore_api", 0]]
                    # [test_var+"oneclickrestore_api", 0]]
            reporting.add_test_script(tests[0][0])
            self.kp = self.create_key_pair(tvaultconf.key_pair_name)
            self.vm_id_1 = self.create_vm(key_pair=self.kp)
            self.vm_id_2 = self.create_vm(key_pair=self.kp)

            # find volume_type = multiattach. So that existing multiattach volume type can be used.
            # Get the volume_type_id
            vol_type_id = -1
            for vol in CONF.volume.volume_types:
                if (vol.lower().find("multiattach") != -1):
                    vol_type_id = CONF.volume.volume_types[vol]
                    vol_type_name = vol

            if (vol_type_id == -1):
                raise Exception("No multiattach volume found to create multiattach volume. Test cannot be continued")

            # Now create volume with derived volume type id...
            self.volume_id = self.create_volume(
                volume_type_id=vol_type_id, size=10,volume_cleanup=False)

            LOG.debug("Volume ID: " + str(self.volume_id))

            self.volumes = []
            self.volumes.append(self.volume_id)
            # Attach volume to vm...
            self.attach_volume(self.volume_id, self.vm_id_1,attach_cleanup=False)
            self.attach_volume(self.volume_id, self.vm_id_2,attach_cleanup=False)
            LOG.debug("Multiattach Volume attached to vm: " + str(self.vm_id_1) + " and " + str(self.vm_id_2))

            vol_vm_1 = self.get_attached_volumes(self.vm_id_1)
            vol_vm_2 = self.get_attached_volumes(self.vm_id_2)
            LOG.debug("Voulme o VM 1: " + str(vol_vm_1) + " on VM 2:" + str(vol_vm_2))
            if vol_vm_1 == vol_vm_2:
                reporting.add_test_step("Attached Multiattach volume to both Instances", tvaultconf.PASS)
                reporting.set_test_script_status(tvaultconf.PASS)
            else:
                reporting.add_test_step("Attached Multiattach volume to both Instances", tvaultconf.FAIL)
                reporting.set_test_script_status(tvaultconf.FAIL)
                raise Exception("Multiattach volume failed to attach existing instance")
            fip = self.get_floating_ips()
            LOG.debug("\nAvailable floating ips are {}: \n".format(fip))

            if len(fip) < 6:
                raise Exception("Floating ips unavailable")
            self.set_floating_ip(fip[0], self.vm_id_1)
            self.set_floating_ip(fip[1], self.vm_id_2)


            md5sums_before_full1, md5sums_before_full1_vol = self._add_data_on_instance_and_volume(fip[0])
            LOG.debug(
                f"md5sums_before_full: {md5sums_before_full1} md5sums_before_full_vol: {md5sums_before_full1_vol}")

            md5sums_before_full2, md5sums_before_full2_vol = self._add_data_on_instance_and_volume(fip[1])
            LOG.debug(
                f"md5sums_before_full: {md5sums_before_full2} md5sums_before_full_vol: {md5sums_before_full2_vol}")

            # Create workload with API
            try:
                self.wid = self.workload_create([self.vm_id_1, self.vm_id_2],
                                                tvaultconf.workload_type_id)
                LOG.debug("Workload ID: " + str(self.wid))
            except Exception as e:
                LOG.error(f"Exception: {e}")
                raise Exception("Create workload " \
                                "with image booted vm")
            if (self.wid is not None):
                self.wait_for_workload_tobe_available(self.wid)
                self.workload_status = self.getWorkloadStatus(self.wid)
                if (self.workload_status == "available"):
                    reporting.add_test_step("Create workload " \
                                            "with image booted vm", tvaultconf.PASS)
                    tests[0][1] = 1
                    reporting.test_case_to_write()
                else:
                    raise Exception("Create workload " \
                                    "with image booted vm")
            else:
                raise Exception("Create workload with image " \
                                "booted vm")

            reporting.add_test_script(tests[1][0])
            self.snapshot_id = self.workload_snapshot(self.wid, True)
            self.wait_for_workload_tobe_available(self.wid)
            self.snapshot_status = self.getSnapshotStatus(self.wid,
                                                          self.snapshot_id)
            if (self.snapshot_status == "available"):
                reporting.add_test_step("Create full snapshot", tvaultconf.PASS)
                self.mount_path = self.get_mountpoint_path(
                    tvaultconf.tvault_ip[0], tvaultconf.tvault_username,
                    tvaultconf.tvault_password)
                self.snapshot_found = self.check_snapshot_exist_on_backend(
                    tvaultconf.tvault_ip[0], tvaultconf.tvault_username,
                    tvaultconf.tvault_password, self.mount_path,
                    self.wid, self.snapshot_id)
                LOG.debug(f"snapshot_found: {self.snapshot_found}")
                if self.snapshot_found:
                    reporting.add_test_step("Verify snapshot existence on " \
                                            "target backend", tvaultconf.PASS)

                    tests[1][1] = 1
                    reporting.test_case_to_write()
                else:
                    raise Exception("Verify snapshot existence on target backend")
            else:
                raise Exception("Create full snapshot")

            reporting.add_test_script(tests[2][0])
            md5sums_before_incr1, md5sums_before_incr1_vol = self._add_data_on_instance_and_volume(fip[0],False)
            LOG.debug(
                f"md5sums_before_incr: {md5sums_before_incr1} md5sums_before_incr_vol: {md5sums_before_incr1_vol}")

            md5sums_before_incr2, md5sums_before_incr2_vol = self._add_data_on_instance_and_volume(fip[1], False)
            LOG.debug(
                f"md5sums_before_incr: {md5sums_before_incr2} md5sums_before_incr_vol: {md5sums_before_incr2_vol}")

            self.snapshot_id2 = self.workload_snapshot(self.wid, False)
            self.wait_for_workload_tobe_available(self.wid)
            self.snapshot_status = self.getSnapshotStatus(self.wid,
                                                          self.snapshot_id2)
            if (self.snapshot_status == "available"):
                reporting.add_test_step("Create incremental snapshot", tvaultconf.PASS)
                self.mount_path = self.get_mountpoint_path(
                    tvaultconf.tvault_ip[0], tvaultconf.tvault_username,
                    tvaultconf.tvault_password)
                self.snapshot_found = self.check_snapshot_exist_on_backend(
                    tvaultconf.tvault_ip[0], tvaultconf.tvault_username,
                    tvaultconf.tvault_password, self.mount_path,
                    self.wid, self.snapshot_id2)
                LOG.debug(f"snapshot_found: {self.snapshot_found}")
                if self.snapshot_found:
                    reporting.add_test_step("Verify snapshot existence on " \
                                            "target backend", tvaultconf.PASS)

                    tests[2][1] = 1
                    reporting.test_case_to_write()
                else:
                    raise Exception("Verify snapshot existence on target backend")
            else:
                raise Exception("Create incremental snapshot")


            # selective restore
            reporting.add_test_script(tests[3][0])
            rest_details = {}
            rest_details['rest_type'] = 'selective'
            rest_details['volume_type'] = vol_type_name
            rest_details['network_id'] = CONF.network.internal_network_id
            rest_details['subnet_id'] = self.get_subnet_id(
                CONF.network.internal_network_id)
            rest_details['instances'] = {self.vm_id_1: self.volumes, self.vm_id_2: self.volumes}

            payload = self.create_restore_json(rest_details)
            # Trigger selective restore of full snapshot
            self._selective_restore(payload,[fip[2],fip[3]],
                                    [md5sums_before_full1, md5sums_before_full1_vol,
                                     md5sums_before_full2, md5sums_before_full2_vol])

            # Trigger selective restore of incremental snapshot
            self._selective_restore(payload, [fip[4], fip[5]],
                                    [md5sums_before_incr1, md5sums_before_incr1_vol,
                                     md5sums_before_incr2,md5sums_before_incr2_vol],
                                    False)
            reporting.test_case_to_write()
            tests[3][1] = 1



            try:
                self.detach_volume(self.vm_id_1, self.volume_id)
            except:
                pass

        except Exception as e:
            LOG.error(f"Exception: {e}")
            reporting.add_test_step(str(e), tvaultconf.FAIL)
            reporting.set_test_script_status(tvaultconf.FAIL)

        finally:
            self.delete_volume(self.volume_id)
            for test in tests:
                if test[1] != 1:
                    reporting.set_test_script_status(tvaultconf.FAIL)
                    reporting.add_test_script(test[0])
                    reporting.test_case_to_write()