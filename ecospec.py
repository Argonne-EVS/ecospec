# -*- coding: utf-8 -*-
#
# ecospec.py - Ecospec Instrumenation Package Main Program
# Copyright (C) 2014  Donald J. Bales, Argonne National Laboratory
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import axis_q1604
import cr_1000
import fieldspec4
import ptu_d300
import os
import sys
import time

class EcoSpec:
	DATA_PATH         = "/home/ecospec/data/"
	LOG_PATH          = "/home/ecospec/log/"
	AXIS_Q1604_HOST   = "146.137.13.119"
	DATA_LOGGER_HOST  = "146.137.13.118"
	SPECTROMETER_HOST = "146.137.13.115"
	PAN_TILT_HOST     = "/dev/ttyUSB0"
	ONE_MINUTE        = 60
	THIRTY_MINUTES    = 30 * 60

	def __init__(self):
		print "Ecospec.__init__()..."
		if not os.path.exists(EcoSpec.DATA_PATH):
			os.makedirs(EcoSpec.DATA_PATH)
		if not os.path.exists(EcoSpec.LOG_PATH):
			os.makedirs(EcoSpec.LOG_PATH)
		self.camera_thread_status     = None
		self.datalogger_thread_status = None
		self.data_set_id              = None
		self.sunrise                  = None
		self.sunset                   = None
		self.dark_current_results     = []
		self.white_reference_results  = []
		self.subject_matter_results   = []
		self.pantilt                  = None
		self.pantilt_position         = -1
		self.pantilt_positions        = [-170, -139, -108, -77, -46, -15, 15, 46, 77, 108, 139, 170]
		self.spectrometer             = None


	def main(self):
		print "EcoSpec.main()..."
		self.sunrise_time = self.calculate_sunrise()
		self.sunset_time  = self.calculate_sunset()

		# Wait until 25 minutes before sunrise, then turn on the 
		# rest of the equipment, in order to warm up the spectrometer
		while time.time() < self.sunrise_time - EcoSpec.THIRTY_MINUTES:
			time.sleep(ONE_MINUTE)

		self.power_up()

		# Wait until sunrise, then start collecting data
		while time.time() < self.sunrise_time:
			time.sleep(EcoSpec.ONE_MINUTE)

		count = 0
		# Collect data until sunset
		while time.time() < self.sunset_time:
			self.activate_pantilt()
			self.activate_spectrometer()
			count += 1
			if count > 2:
				break

		self.power_down()

		exit(0)


	def get_next_position(self, current_position):
		if current_position < 11:
			next_position = current_position + 1
		else:
			next_position = 0

		return next_position


	def activate_pantilt(self):
		# A serial communications device
		print "EcoSpec.activate_pantilt()..."

		if not self.pantilt:
			self.pantilt = ptu_d300.PtuD300('/dev/ttyUSB0', 38400)

		self.pantilt_position = get_next_position(self.pantilt_position)

		if self.pantilt_position == 0:
			self.pantilt.send(ptu_d300.PtuD300.STATUS_QUERY)
			self.pantilt.send(ptu_d300.PtuD300.PAN_SPEED_ABSOLUTE + str(self.pantilt.pan_speed_maximum))
		else:
			self.pantilt.send(ptu_d300.PtuD300.PAN_SPEED_ABSOLUTE + str(1000))

		self.pantilt.send(ptu_d300.PtuD300.PAN_IMMEDIATELY)

		self.pantilt.send(ptu_d300.PtuD300.PAN_POSITION_ABSOLUTE + str(self.pantilt.degrees_to_positions(positions[self.pantilt_position])))

		result = self.pantilt.send(ptu_d300.PtuD300.PAN_AWAIT_COMPLETION)
		#print("result: '" + result +"'")
		#print(result[2:4])
		#if result[2:4] == "!P":
		if "!P" in result:
			print("trying again...")
			self.pantilt.send(ptu_d300.PtuD300.PAN_POSITION_ABSOLUTE)
			self.pantilt.send(ptu_d300.PtuD300.PAN_POSITION_ABSOLUTE + str(self.pantilt.degrees_to_positions(positions[self.pantilt_position])))
			self.pantilt.send(ptu_d300.PtuD300.PAN_AWAIT_COMPLETION)

		return True


	def activate_spectrometer(self):
		# TCP/IP communications device
		print "EcoSpec.activate_spectrometer()..."

		try:
			if not self.spectrometer:
				self.spectrometer = fieldspec4.FieldSpec4()

			print self.spectrometer

			self.spectrometer.open(EcoSpec.SPECTROMETER_HOST)

			version = self.spectrometer.version()

			print "version.name: " + version.name
			print "version.value: " + str(version.value)
			print "version.type: " + str(version.type)

			restore = self.spectrometer.restore("1")

			if restore.header != 100:
				restore = self.spectrometer.restore("1")

			print "restore.header: " + str(restore.header)
			print "restore.errbyte: " + str(restore.errbyte)
			for i in range(0, 200):
				if restore.names[i]:
					print restore.names[i] + ": " + str(restore.values[i])
			print "restore.count: " + str(restore.count)
			print "restore.verify: " + str(restore.verify)

			"""
			a = self.spectrometer.abort()

			print "abort.header: " + str(a.header)
			print "abort.errbyte: " + str(a.errbyte)
			print "abort.name: " + a.name
			print "abort.value: " + str(a.value)
			print "abort.count: " + str(a.count)

			"""

			self.extend_white_reference_arm()

			# Optimize the spectrometer with the white reference in field of view
			
			optimize = self.spectrometer.optimize(fieldspec4.FieldSpec4.OPT_VNIR_SWIR1_SWIR2)

			print "optimize.header: " + str(optimize.header)
			print "optimize.errbyte: " + str(optimize.errbyte)
			print "optimize.itime: " + str(optimize.itime)
			print "optimize.gain1: " + str(optimize.gain1)
			print "optimize.gain2: " + str(optimize.gain2)
			print "optimize.offset1: " + str(optimize.offset1)
			print "optimize.offset2: " + str(optimize.offset2)

			# Open the shutter and collect 10 white reference readings
			acquire = None
			if optimize.header == 100:
				acquire = self.spectrometer.acquire(fieldspec4.FieldSpec4.ACQUIRE_SET_SAMPLE_COUNT, "10", "0")
				print "acquire.spectrum_header.header: " + str(acquire.spectrum_header.header)
				print "acquire.spectrum_header.errbyte: " + str(acquire.spectrum_header.errbyte)
				print "acquire.spectrum_header.sample_count: " + str(acquire.spectrum_header.sample_count)
				print "acquire.spectrum_header.trigger: " + str(acquire.spectrum_header.trigger)
				print "acquire.spectrum_header.voltage: " + str(acquire.spectrum_header.voltage)
				print "acquire.spectrum_buffer length: " + str(len(acquire.spectrum_buffer))
				spectrum_data = "spectrum_data: " + str(acquire.spectrum_buffer[0]) 
				for i in range(1, len(acquire.spectrum_buffer)):
					spectrum_data += ","
					spectrum_data += str(acquire.spectrum_buffer[i])
				print spectrum_data

			# Close the shutter and collect 25 dark current readings 
			# TODO
			control = None
			if optimize.header == 100 and acquire.spectrum_header.header == 100:
				control = self.spectrometer.control(fieldspec4.FieldSpec4.CONTROL_VNIR, fieldspec4.FieldSpec4.CONTROL_SHUTTER, fieldspec4.FieldSpec4.CLOSE_SHUTTER)
				print "control.header: " + str(control.header)
				if control.header == 100:
					acquire = self.spectrometer.acquire(fieldspec4.FieldSpec4.ACQUIRE_SET_SAMPLE_COUNT, "25", "0")
					print "acquire.spectrum_header.header: " + str(acquire.spectrum_header.header)
					print "acquire.spectrum_header.errbyte: " + str(acquire.spectrum_header.errbyte)
					print "acquire.spectrum_header.sample_count: " + str(acquire.spectrum_header.sample_count)
					print "acquire.spectrum_header.trigger: " + str(acquire.spectrum_header.trigger)
					print "acquire.spectrum_header.voltage: " + str(acquire.spectrum_header.voltage)
					print "acquire.spectrum_buffer length: " + str(len(acquire.spectrum_buffer))
					spectrum_data = "spectrum_data: " + str(acquire.spectrum_buffer[0]) 
					for i in range(1, len(acquire.spectrum_buffer)):
						spectrum_data += ","
						spectrum_data += str(acquire.spectrum_buffer[i])
					print spectrum_data
				control = self.spectrometer.control(fieldspec4.FieldSpec4.CONTROL_VNIR, fieldspec4.FieldSpec4.CONTROL_SHUTTER, fieldspec4.FieldSpec4.OPEN_SHUTTER)
				print "control.header: " + str(control.header)

			self.retract_white_reference_arm()
			self.data_set_id = time.strftime("%Y%m%d%H%M%S")
			self.activate_camera()
			self.activate_datalogger()

			# Open the shutter and collect 10 subject matter readings

			if optimize.header == 100 and acquire.spectrum_header.header == 100 and control.header == 100:
				acquire = self.spectrometer.acquire(fieldspec4.FieldSpec4.ACQUIRE_SET_SAMPLE_COUNT, "10", "0")
				print "acquire.spectrum_header.header: " + str(acquire.spectrum_header.header)
				print "acquire.spectrum_header.errbyte: " + str(acquire.spectrum_header.errbyte)
				print "acquire.spectrum_header.sample_count: " + str(acquire.spectrum_header.sample_count)
				print "acquire.spectrum_header.trigger: " + str(acquire.spectrum_header.trigger)
				print "acquire.spectrum_header.voltage: " + str(acquire.spectrum_header.voltage)
				print "acquire.spectrum_buffer length: " + str(len(acquire.spectrum_buffer))
				spectrum_data = "spectrum_data: " + str(acquire.spectrum_buffer[0]) 
				for i in range(1, len(acquire.spectrum_buffer)):
					spectrum_data += ","
					spectrum_data += str(acquire.spectrum_buffer[i])
				print spectrum_data

			self.save_spectrometer_readings()
			self.spectrometer.close()

			# Wait for the camera and data logger to finish up
#			while self.camera_thread_status     < 1 and \
#			      self.datalogger_thread_status < 1:
#			    time.sleep(1)
		except:
			print "EcoSpec.activate_spectrometer(): ERROR:"
			print "sys.exc_type: " + str(sys.exc_type)
			print "sys.exc_value: " + str(sys.exc_value)
			print "sys.exc_traceback: " + str(sys.exc_traceback)
			print "sys.exc_info(): " + str(sys.exc_info())

		return True


	def activate_camera(self):
		# TCP/IP communications device
		print "EcoSpec.activate_camera()..."

		camera = axis_q1604.AxisQ1604(self.data_set_id, EcoSpec.AXIS_Q1604_HOST)

		return True


	def activate_datalogger(self):
		# A serial communications device
		print "EcoSpec.activate_datalogger()..."

		data_logger = cr_1000.CR1000(self.data_set_id, EcoSpec.DATA_LOGGER_HOST)

		return True


	def calculate_sunrise(self):
		print "EcoSpec.calculate_sunrise()..."
		now_tuple = time.localtime()
		now_list = list(now_tuple)
		now_list[3] = 5
		now_list[4] = 0
		now_list[5] = 0
		result = time.mktime(tuple(now_list))
		return result


	def calculate_sunset(self):
		print "EcoSpec.calculate_sunset()..."
		now_tuple = time.localtime()
		now_list = list(now_tuple)
		now_list[3] = 19
		now_list[4] = 0
		now_list[5] = 0
		result = time.mktime(tuple(now_list))
		return result


	def extend_white_reference_arm(self):
		print "EcoSpec.extend_white_reference_arm()..."
		# TODO:
		return True


	def power_down(self):
		print "EcoSpec.power_down()..."
		# TODO:
		return True


	def power_up(self):
		print "EcoSpec.power_up()..."
		# TODO: 
		return True


	def retract_white_reference_arm(self):
		print "EcoSpec.retract_white_reference_arm()..."
		# TODO: 
		return True


	def save_spectrometer_readings(self):
		print "EcoSpec.save_spectrometer_readings()..."
		file_name = EcoSpec.DATA_PATH + self.data_set_id + "_spectrometer" + "_wr.tsv"
		file_handle = open(file_name, "a")
		for i in range(0, len(self.white_reference_results)):
			file_handle.write(self.data_set_id + "\t" + "0" + "\t" + self.white_reference_results[i])
		file_handle.close()

		file_name = EcoSpec.DATA_PATH + self.data_set_id + "_spectrometer" + "_dc.tsv"
		file_handle = open(file_name, "a")
		for i in range(0, len(self.dark_current_results)):
			file_handle.write(self.data_set_id + "\t" + "0" + "\t" + self.dark_current_results[i])
		file_handle.close()

		file_name = EcoSpec.DATA_PATH + self.data_set_id + "_spectrometer" + "_sm.tsv"
		file_handle = open(file_name, "a")
		for i in range(0, len(self.subject_matter_results)):
			file_handle.write(self.data_set_id + "\t" + "0" + "\t" + self.subject_matter_results[i])
		file_handle.close()
		return True


if __name__ == '__main__':
    main()
