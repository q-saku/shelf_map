#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This script helps with identification of disk in the shelf.
It allows to set ident on/off mode for disk in the slot of particular
shelf.
For default it shows a map of devices.

Supported operating systems: FreeBSD, Linux
Requirements: sysutils/sg3_utils(for FreeBSD), sg3-utils(for Linux)

Author: Aleksandr Kurnosov <q-saku@ya.ru>
"""

import glob
import re
import sys
import os
import subprocess
from optparse import OptionParser


class Shelf(object):
    """
    Class for collecting information about shelves and containing information
    about drives.
    """
    def __init__(self, name, controller_type):
        self.name = name
        self.type = controller_type
        self.drives = {}


class ShelfUnit(object):

    """
    Class for collecting information about shelves and drives.
    """

    def __init__(self, name='Empty',
                 slot='No data',
                 sas='No data',
                 sn='No data',
                 ident='No data',
                 expander='No data',
                 shelf_id='No data'):
        self.name = name
        self.sn = sn
        self.slot = slot
        self.ident = ident
        self.sas = sas
        self.expander = expander
        self.shelf_id = shelf_id
        self.locate_unit = ''

    def __str__(self):
        if self.ident == '0':
            self.locate_unit = col('white', 'Off')
        elif self.ident == '1':
            self.locate_unit = col('green', 'On')

        return ('DRIVE: %-19sSHELF: %-14sSLOT: %-14sLOCATE: %-16sSERIAL: %-s' %
                (col('white', self.name), col('white', self.shelf_id),
                 col('white', self.slot), self.locate_unit,
                 col('white', self.sn)))

    def locate(self, status):
        """
        Locate target disk. Requires 1 argument with values 'on' or 'clear'
        """
        if status == 'on':
            if self.ident == '0':
                subprocess.Popen('sudo sg_ses --index=%s --set=ident /dev/%s' %
                                 (self.slot, self.expander),
                                 shell=True)
                message('msg', 'SHELF: %-2s SLOT: %-2s | Setting LOCATE in %s.'
                               % (self.shelf_id, self.slot, col('green', 'On')))
                self.ident = '1'
            else:
                message('warn', 'SHELF: %-2s SLOT: %-2s | Disk already located.'
                                % (self.shelf_id, self.slot))

        elif status == 'clear':
            if self.ident == '1':
                subprocess.Popen('sudo sg_ses --index=%s --clear=ident '
                                 '/dev/%s' %
                                 (self.slot, self.expander), shell=True)
                message('msg', 'SHELF: %-2s SLOT: %-2s | Setting LOCATE in %s.'
                               % (self.shelf_id, self.slot,
                                  col('white', 'Off')))
                self.ident = '0'


# MESSAGES AND COLORS
def message(message_type, text):
    """
    Handling service messages.
    """
    if message_type == 'error':
        sys.stderr.write('| ' + col('red', 'ERROR') + ' | ' + text + '\n')

    elif message_type == 'warn':
        sys.stderr.write('| ' + col('yellow', 'WARNING') + ' | ' + text + '\n')
    else:
        sys.stderr.write('| ' + col('green', 'MESSAGE') + ' | ' + text + '\n')


def col(color, text):
    """
    Paints the specified text to the specified color.
    Requires 2 arguments: color and text.
    """
    end = '\033[0m'
    if 'red' in color:
        color = '\033[91m'
    elif 'gray' in color:
        color = '\033[90m'
    elif 'green' in color:
        color = '\033[92m'
    elif 'blue' in color:
        color = '\033[94m'
    elif 'white' in color:
        color = '\033[97m'
    elif 'yellow' in color:
        color = '\033[93m'
    return color + str(text) + end


# PARSERS
def expander_parser(ses_out, ses_ident_out, storage_id, expander):
    """
    Takes output from sg_ses utils pages 2 and 0xA and compare dict with
    following fields: SHELF_ID, BAY, IDENT and SAS ADDRESS as key.
    """
    # PARSING PAIR: SAS ADDRESS - BAY
    expander_data = {}
    bay = ''
    for line in ses_out:
        if 'lement index:' in line:
            bay = line.split()[2]
        elif 'lement' in line and 'descriptor' in line:
            bay = line.split()[1]
        if 'SAS address:' in line:
            sas_address = line.split()[-1]
            if sas_address == '0x0000000000000000':
                sas_address = 'EMPTY' + str(storage_id) + str(bay)
            expander_data[sas_address] = {'SHELF_ID': storage_id,
                                          'BAY': bay,
                                          'EXPANDER': expander}
    # Check for empty expander.
    if not expander_data:
        return
    # PARSING PAIR: BAY - IDENT
    # Output has separated by sections and keywords 'Element descriptor'
    # are repeated constatnly.
    section_count = 0
    for line in ses_ident_out:
        if 'Element type:' in line:
            section_count += 1
            if section_count == 2:
                break
        if 'Element' in line and 'descriptor' in line:
            bay = line.split()[1]
        elif 'element' in line and 'Individual' in line:
            bay = str(int(line.split()[2]) - 1)
        if 'Ident' in line:
            ident = line.split(',')[2].split('=')[-1]
    # COMPARE SAS - BAY - IDENT
    # we need to skip first 'ident' and wait to determine variable 'bay'
            if bay:
                for sas_address in expander_data:
                    if expander_data[sas_address]['BAY'] == bay:
                        expander_data[sas_address]['IDENT'] = ident
    return expander_data


def disk_parser(vdp_out, field_type):
    """
    Takes output from sg_vdp utility and get SAS ADDRESS or SERIAL NUMBER
    of disk unit.
    """
    if field_type == 'sas':
        for line in vdp_out:
            if re.search('^\s+0x', line):
                return line.split()
        return '0x0000000000000000'
    elif field_type == 'sn':
        for line in vdp_out:
            if 'Unit serial number:' in line:
                return line.split()[-1]
        return 'No data'


# SHELF/DISK FUNCTIONS
def find_devices(pattern):
    """
    Gets list of devices determined by pattern: shelves or drives.
    For FreeBSD uses native methods.
    For Linux uses part of sg3_utils package - sg_map.
    """
    if 'freebsd' in sys.platform:
        if pattern == 'disk':
            return glob.glob1('/dev/',
                              'da[0-9]') + glob.glob1('/dev/',
                                                      'da[0-9][0-9]')
        elif pattern == 'shelf':
            return glob.glob1('/dev/', 'ses*')

    elif 'linux' in sys.platform:
        device_list = subprocess.Popen('sudo sg_map -x',
                                       shell=True,
                                       stdout=subprocess.PIPE
                                       ).stdout.readlines()
        if pattern == 'disk':
            disklist = []
            for device in device_list:
                device = device.split()
                if '13' not in device[5]:
                    try:
                        disklist.append(device[6][5:])
                    except IndexError:
                        pass
            return disklist

        elif pattern == 'shelf':
            shelflist = []
            for device in device_list:
                device = device.split()
                if '13' in device[5]:
                    shelflist.append(device[0][5:])
            return shelflist


def get_disk_info(disk_list):
    """
    Analyzes every disk from the disk_list. Gets information about every
    disk. Collects and associates disk, sas_address and serial_number.
    """
    disk_data = {}
    for disk in disk_list:
        vdp_sas = subprocess.Popen('sudo sg_vpd -p di_port /dev/' + disk,
                                   shell=True,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE).stdout.readlines()
        vdp_sn = subprocess.Popen('sudo sg_vpd -p sn /dev/' + disk,
                                  shell=True,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE).stdout.readlines()
        sas_address = disk_parser(vdp_sas, 'sas')[0]
        serial_number = disk_parser(vdp_sn, 'sn')

        disk_data[disk] = ShelfUnit(name=disk, sas=sas_address,
                                    sn=serial_number)
    return disk_data


def compare_shelf_map(shelf_list, disk_data, controller_type='HBA'):
    """
    Looks through at each shelf from shelf_list. Gets information
    about every slot of every shelf. Also associates slot and drive using
    SAS ADDRESS with transferring all information in dict() of objects.
    """
    shelf_data = {}
    shelf_count = 0
    for shelf in shelf_list:
        shelf_count += 1
        ses_out = subprocess.Popen('sudo sg_ses -p 0xA /dev/' + shelf,
                                   shell=True,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE).stdout.readlines()
        ses_ident_out = subprocess.Popen('sudo sg_ses -p 2 /dev/' + shelf,
                                         shell=True,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE
                                         ).stdout.readlines()
        bays = expander_parser(ses_out, ses_ident_out, shelf_count, shelf)
    # Check for empty expander.
        if not bays:
            continue
        shelf_data[shelf] = Shelf(shelf_count,
                                  controller_type=controller_type)
    # Collect result, using matched SAS address.
        for sas in bays:
            if 'EMPTY' in sas:
                shelf_data[shelf].drives[sas] = ShelfUnit(
                    name=sas, shelf_id=bays[sas]['SHELF_ID'],
                    slot=bays[sas]['BAY'], expander=bays[sas]['EXPANDER'],
                    ident=bays[sas]['IDENT'])
                continue
            for disk in disk_data:
                if sas in disk_data[disk].sas:
                    shelf_data[shelf].drives[disk] = ShelfUnit(
                        name=disk, sas=sas, shelf_id=bays[sas]['SHELF_ID'],
                        slot=bays[sas]['BAY'], expander=bays[sas]['EXPANDER'],
                        ident=bays[sas].get('IDENT', ''),
                        sn=disk_data[disk].sn)
                    break
    return shelf_data


# MANAGE FUNCTIONS
def manage_ident(shelf_data, arg, options):
    """
    Manage ident using the specific options.
    """
    for shelf in shelf_data:
        for disk in shelf_data[shelf].drives:
            if options.empty:
                if 'EMPTY' in disk:
                    shelf_data[shelf].drives[disk].locate(arg)
            if options.all_drives:
                shelf_data[shelf].drives[disk].locate(arg)
            elif options.drive and options.drive in shelf_data[shelf].drives:
                shelf_data[shelf].drives[options.drive].locate(arg)
                break


# CHECK FUNCTIONS
def sg3utils_check():
    """
    Check for installed package sysutils/sg3_utils.
    """
    if 'freebsd' in sys.platform:
        pkg_info_out = subprocess.Popen('pkg info', shell=True,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE
                                        ).stdout.readlines()
        for package in pkg_info_out:
            if 'sg3_utils' in package:
                return
        message('error', 'Package "sg3_utils" is not found. Install his first.')
        exit(1)
    elif 'darwin' in sys.platform:
        message('error', 'Script was not support MacOS X.')
        exit(1)
    elif 'linux' in sys.platform:
        # Check skipped for capability with any linux platforms
        return


def check_user():
    """
    Checks for user root running. Package sg3_utils requires root permissions.
    """
    if os.getuid() != 0:
        message('error', 'Script should be run as root user.')
        sys.exit(1)


def check_args(options, args, disk_data):
    """
    Checks for sys.argv and updates existing options.
    """
    if len(sys.argv) > 2:
        disk_arg = args[0]
        if disk_arg == 'all':
            options.all_drives = True
        elif disk_arg == 'empty':
            options.empty = True
        else:
            if '/dev/' in disk_arg:
                disk_arg = disk_arg[5:]

            if disk_arg in disk_data:
                options.drive = disk_arg
            else:
                message('error', 'Disk %s was not found in system.'
                                 % (col('white', disk_arg)))
                exit(1)
    return options


# ACTIONS
def make_action(drives_data, options):
    """
    Generates actions according specify options.
    """
    if (not options.clear_ident and not options.locate_disk and not
        options.empty or options.print_table and not
            options.locate_disk and not options.empty):
        for shelf in drives_data:
            for disk in sorted(drives_data[shelf].drives,
                               key=lambda drive:
                               int(drives_data[shelf].drives[drive].slot)):
                print(drives_data[shelf].drives[disk])
    try:
        if options.locate_disk and not options.print_table:
            manage_ident(drives_data, 'on', options)
        elif options.locate_disk and options.print_table:
            for shelf in drives_data:
                for disk in drives_data[shelf].drives:
                    if drives_data[shelf].drives[disk].ident == '1':
                        print(drives_data[shelf].drives[disk])
        elif options.empty and options.print_table:
            for shelf in drives_data:
                for disk in drives_data[shelf].drives:
                    if 'EMPTY' in disk:
                        print(drives_data[shelf].drives[disk])
        if options.clear_ident:
            manage_ident(drives_data, 'clear', options)
    except KeyError:
        message('error', 'Cannot get information about drive: %s '
                         % (col('white', options.drive)))


# OPTIONS
def parse_options():
    opts = OptionParser(usage="Usage: %prog [options] [drive]",
                        version='%prog 1.06',
                        description="""
Description: This script helps with identification of disk in the shelf.
It allows to set ident on/off mode for disk in the slot of particular
shelf.
For default shows map of devices.
""",
                        epilog="""
Additional: Requires package sysutils/sg3_utils(for FreeBSD) or
sg3-utils(for Linux) installed on your system. And root permissions for use it.

""")

    opts.add_option('-p', '--print', action='store_true',
                    dest='print_table', default=False,
                    help='prints map of devices')
    opts.add_option('-l', '--locate', action='store_true',
                    dest='locate_disk', default=False,
                    help='sets ident for specify disk')
    opts.add_option('-c', '--clear', action='store_true',
                    dest='clear_ident', default=False,
                    help='clears ident for specify or all disks')
    opts.add_option('-a', '--all', action='store_true',
                    dest='all_drives', default=False,
                    help='sets action for all devices')
    opts.add_option('-e', '--empty', action='store_true',
                    dest='empty', default=False,
                    help='sets action for all empty slots')
    (opts, args) = opts.parse_args()

    opts.drive = ''

    return opts, args


def main():
    # GET BASIC INFORMATION
    disk_list = find_devices('disk')
    shelf_list = find_devices('shelf')

    # GET SHELF MAP
    disk_data = get_disk_info(disk_list)
    shelf_data = compare_shelf_map(shelf_list, disk_data)

    if __name__ == '__main__':
        # PARSE OPTIONS
        (options, arguments) = parse_options()

        # CHECK FOR INSTALLED sg3_utils PACKAGE
        sg3utils_check()

        # CHECK FOR ROOT USER
        check_user()

        # UPDATE OPTIONS FROM sys.argv
        options = check_args(options, arguments, disk_data)

        # ACTIONS
        make_action(shelf_data, options)
    else:
        return shelf_data


if __name__ == '__main__':
    main()
