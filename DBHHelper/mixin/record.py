import time
from typing import override

import obsws_python as obs

from core.event import EventDispatcher, EventSystemCloseEvent, EventSystemStartEvent
from DBHHelper.api import DBHHelperAPI


def get_properties_string(obj):
    """
    Returns a one-line string of all non-callable properties of the object.

    Args:
    obj (object): The object to inspect.

    Returns:
    str: A comma-separated string of properties in the format 'attribute: value'.
    """
    return ", ".join(
        f"{attribute}: {getattr(obj, attribute)}"
        for attribute in dir(obj)
        if not callable(getattr(obj, attribute)) and not attribute.startswith("__")
    )


class OBSRecorderMixin(DBHHelperAPI, EventDispatcher):
    @override
    def recorder_setup(self, record=False, change_rec_dir=True):
        if not record:
            return
        self.obs_cl = obs.ReqClient(host="localhost", port=4455, password="", timeout=3)
        self.debug(f"OBS Version: {self.obs_cl.get_version().obs_version}")
        if change_rec_dir:
            ret = self.obs_cl.get_record_directory()
            self.original_record_directory = ret.record_directory
            self.debug(f"Current record directory: {self.original_record_directory}")
            self.obs_cl.set_record_directory(f"{self._logger.log_path}")
            ret = self.obs_cl.get_record_directory()
            self.debug(f"New record directory: {ret.record_directory}")
        self.record_start = False
        self.record_active = False

    @EventDispatcher.on(EventSystemStartEvent)
    @override
    def start_record(self):
        if not hasattr(self, "obs_cl") or self.record_start:
            return
        self.obs_cl.start_record()
        self.record_start = True
        self.record_active = True
        self.debug("Recording started.")

    @override
    def pause_record(self):
        if (
            not hasattr(self, "obs_cl")
            or not self.record_start
            or not self.record_active
        ):
            return
        self.debug("Pausing recording...")
        while True:
            try:
                ret = self.obs_cl.get_record_status()
                self.debug(f"Record status: {get_properties_string(ret)}")
                if ret.output_paused:
                    self.debug("Recording already paused.")
                    break
                self.obs_cl.pause_record()
                time.sleep(0.1)
                ret = self.obs_cl.get_record_status()
                self.debug(f"Record status: {get_properties_string(ret)}")
                if ret.output_paused:
                    break
            except Exception as e:
                self.error(f"Failed to pause recording: {e}")
            time.sleep(0.1)
        self.record_active = False
        self.debug("Recording paused.")

    @override
    def resume_record(self):
        if not hasattr(self, "obs_cl") or not self.record_start or self.record_active:
            return
        self.debug("Resuming recording...")
        while True:
            try:
                ret = self.obs_cl.get_record_status()
                self.debug(f"Record status: {get_properties_string(ret)}")
                if not ret.output_paused:
                    self.debug("Recording already resumed.")
                    break
                self.obs_cl.resume_record()
                time.sleep(0.1)
                ret = self.obs_cl.get_record_status()
                self.debug(f"Record status: {get_properties_string(ret)}")
                if not ret.output_paused:
                    break
            except Exception as e:
                self.error(f"Failed to resume recording: {e}")
            time.sleep(0.1)
        self.record_active = True
        self.debug("Recording resumed.")

    @EventDispatcher.on(EventSystemCloseEvent)
    @override
    def stop_record(self):
        if not hasattr(self, "obs_cl") or not self.record_start:
            return
        retStop = None
        while True:
            try:
                ret = self.obs_cl.get_record_status()
                self.debug(f"Record status: {get_properties_string(ret)}")
                if not ret.output_active:
                    break
                ret = self.obs_cl.stop_record()
                retStop = ret
                time.sleep(1)
            except Exception as e:
                pass
            time.sleep(1)
        self.record_start = False
        self.record_active = False
        self.debug("Recording stopped.")
        if retStop:
            self.info(f"Recording saved to {retStop.output_path}")
        self.obs_cl.set_record_directory(self.original_record_directory)
        self.debug(f"Record directory reset to {self.original_record_directory}")

    @override
    def get_version(self):
        if not hasattr(self, "obs_cl"):
            return
        resp = self.obs_cl.get_version()
        return resp.obs_version
