#!/usr/bin/env python

# Copyright (C) 2018 The University of Leeds
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Rafael Papallas (rpapallas.com)

"""Extends OpenRAVE Robot

This class is an extension of OpenRAVE's Robot to include some handy functions.
"""

__author__ = "Rafael Papallas"
__authors__ = ["Rafael Papallas"]
__copyright__ = "Copyright (C) 2018, The University of Leeds"
__credits__ = ["Rafael Papallas", "Dr. Mehmet Dogar"]
__email__ = "Rafael: r.papallas@leeds.ac.uk  |  Mehmet: m.r.dogar@leeds.ac.uk"
__license__ = "GPLv3"
__maintainer__ = "Rafael Papallas"
__status__ = "Production"
__version__ = "0.0.1"

from openravepy import databases
from openravepy import IkParameterization
from openravepy import interfaces
from openravepy import RaveCreateController
from openravepy import RaveCreateMultiController
from openravepy import RaveLogInfo
from openravepy import Robot
import time


class UR5_Robot(Robot):
    def __init__(self, is_in_simulation, has_gripper):
        self.robot_name = "UR5"
        self._OPENRAVE_GRIPPER_MAX_VALUE = 0.715584844
        self._ROBOT_GRIPPER_MAX_VALUE = 255
        self.is_in_simulation = is_in_simulation
        self._has_gripper = has_gripper

        if not self.is_in_simulation:
            self.multicontroller = RaveCreateMultiController(self.GetEnv(), "")
            self.SetController(self.multicontroller)

        self.manipulator = self.SetActiveManipulator(self.GetManipulators()[0])

        if self._has_gripper:
            # Needed for "find a grasp" function (not parsed using or_urdf hence
            # needs manual setting)
            self.manipulator.SetChuckingDirection([1.0])
            self.manipulator.SetLocalToolDirection([1.0, 0, 0])

        self.ikmodel = databases.inversekinematics.InverseKinematicsModel(
            self, iktype=IkParameterization.Type.Transform6D
        )

        if not self.ikmodel.load():
            RaveLogInfo(
                "The IKModel for UR5 robot is now being generated. "
                "Please be patient, this will take a while "
                "(sometimes up to 30 minutes)..."
            )

            self.ikmodel.autogenerate()

        self.task_manipulation = interfaces.TaskManipulation(self)
        self.base_manipulation = interfaces.BaseManipulation(self)

    @property
    def end_effector_transform(self):
        """End-Effector's current transform property."""
        return self.manipulator.GetTransform()

    def is_gripper_fully_open(self):
        if not self._has_gripper:
            raise Exception(
                "You are trying to use a gripper function while a gripper is not available on your UR5 robot."
            )

        return self.GetDOFValues()[3] == 0

    def is_gripper_fully_closed(self):
        if not self._has_gripper:
            raise Exception(
                "You are trying to use a gripper function while a gripper is not available on your UR5 robot."
            )

        return abs(self.GetDOFValues()[3] - self._OPENRAVE_GRIPPER_MAX_VALUE) <= 0.00001

    def attach_controller(self, name, dof_indices):
        controller = RaveCreateController(self.GetEnv(), name)

        if controller is not None:
            # Attaching the multicontroller now since we know that a
            # valid controller has been created. If multicontroller is
            # set to the robot with no controller attached to the
            # multicontroller, then OpenRAVE will fail to execute any
            # trajectories in simulation, setting the multicontroller now
            # ensures that this won't happen.
            self.multicontroller.AttachController(controller, dof_indices, 0)
            return True

        return False

    def set_gripper_openning(self, value):
        """
        Opens/Closes the gripper by a desired value.

        Args:
            value: Opens/Closes the finger.

        Raises:
            ValueError: If the value is out of bounds [0, 255].

        """
        if not self._has_gripper:
            raise Exception(
                "You are trying to use a gripper function while a gripper is not available on your UR5 robot."
            )

        if value < 0 or value > 255:
            raise ValueError("Gripper value should be between 0 and 255.")

        # This conversion is required because SetDesired() controller
        # requires the value to be in terms of a value between 0 and
        # 0.87266444 (OpenRAVE model limit values) and then is converting
        # it to a value between 0-255 for the low-level gripper driver.
        # To make this method more user-friendly, the value is expected
        # to be between 0 and 255, then we map it down to 0 to 0.87266444
        # and send it to the gripper controller.
        model_value = (
            self._OPENRAVE_GRIPPER_MAX_VALUE
            / self._ROBOT_GRIPPER_MAX_VALUE
            * abs(value)
        )
        dof_values = self.GetDOFValues()
        dof_values[3] = model_value

        self.GetController().SetDesired(dof_values)
        self.WaitForController(0)
        time.sleep(2)

    def _set_dof_value(self, index, value):
        dof_values = self.GetDOFValues()
        dof_values[index] = value
        self.SetDOFValues(dof_values)

    def open_gripper(self, kinbody=None, execute=True):
        """
        Opens end-effector's fingers.

        OpenRAVE Kinbodies can be attached to the end-effector, if you want
        to release an attached kinbody after the fingers are opened, then pass
        that kinbody in this function.

        Args:
            kinbody: Pass an OpenRAVE Kinbody to release after the fingers are
                     opened.
            execute: By default is set to True. Pass False if you want to avoid
                     execution.
        """
        if not self._has_gripper:
            raise Exception(
                "You are trying to use a gripper function while a gripper is not available on your UR5 robot."
            )

        if not execute:
            self._set_dof_value(3, 0.0)
            if kinbody is not None:
                self.Release(kinbody)

            return

        if self.is_in_simulation:
            self.task_manipulation.ReleaseFingers(target=kinbody)
            self.WaitForController(0)
        else:
            self.set_gripper_openning(0)
            if kinbody is not None:
                self.Release(kinbody)

    def close_gripper(self, execute=True):
        """
        Closes end-effector's fingers.

        Args:
            execute: By default is set to True. Pass False if you want to avoid
                     execution.
        """

        if not self._has_gripper:
            raise Exception(
                "You are trying to use a gripper function while a gripper is not available on your UR5 robot."
            )

        if not execute:
            self._set_dof_value(3, self._OPENRAVE_GRIPPER_MAX_VALUE)
            return

        if self.is_in_simulation:
            self.task_manipulation.CloseFingers()
            self.WaitForController(0)
        else:
            self.set_gripper_openning(255)

    def execute_trajectory_and_wait_for_controller(self, trajectory):
        """
        Executes a trajectory and waits for the controller to finish.

        Args:
            trajectory: An OpenRAVE trajectory to execute.
        """
        self.GetController().SetPath(trajectory)
        self.WaitForController(0)
        time.sleep(2)
