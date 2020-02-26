#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
 * **************************************************************************
 * Contributions to this work were made on behalf of the GÉANT project,
 * a project that has received funding from the European Union’s Framework
 * Programme 7 under Grant Agreements No. 238875 (GN3)
 * and No. 605243 (GN3plus), Horizon 2020 research and innovation programme
 * under Grant Agreements No. 691567 (GN4-1) and No. 731122 (GN4-2).
 * On behalf of the aforementioned projects, GEANT Association is
 * the sole owner of the copyright in all material which was developed
 * by a member of the GÉANT project.
 * GÉANT Vereniging (Association) is registered with the Chamber of
 * Commerce in Amsterdam with registration number 40535155 and operates
 * in the UK as a branch of GÉANT Vereniging.
 * 
 * Registered office: Hoekenrode 3, 1102BR Amsterdam, The Netherlands.
 * UK branch address: City House, 126-130 Hills Road, Cambridge CB2 1PQ, UK
 *
 * License: see the web/copyright.inc.php file in the file structure or
 *          <base_url>/copyright.php after deploying the software

Authors:
    Tomasz Wolniewicz <twoln@umk.pl>
    Michał Gasewicz <genn@umk.pl> (Network Manager support)

Contributors:
    Steffen Klemer https://github.com/sklemer1
    ikerb7 https://github.com/ikreb7
Many thanks for multiple code fixes, feature ideas, styling remarks
much of the code provided by them in the form of pull requests
has been incorporated into the final form of this script.

This script is the main body of the CAT Linux installer.
In the generation process configuration settings are added
as well as messages which are getting translated into the language
selected by the user.

The script is meant to run both under python 2.7 and python3. It tests
for the crucial dbus module and if it does not find it and if it is not
running python3 it will try rerunning iself again with python3.
"""
import argparse
import base64
import getpass
import os
import re
import subprocess
import sys
import uuid
from shutil import copyfile

NM_AVAILABLE = True
CRYPTO_AVAILABLE = True
DEBUG_ON = False
DEV_NULL = open("/dev/null", "w")
STDERR_REDIR = DEV_NULL


def debug(msg):
    """Print debugging messages to stdout"""
    if not DEBUG_ON:
        return
    print("DEBUG:" + str(msg))


def missing_dbus():
    """Handle missing dbus module"""
    global NM_AVAILABLE
    debug("Cannot import the dbus module")
    NM_AVAILABLE = False


def byte_to_string(barray):
    """conversion utility"""
    return "".join([chr(x) for x in barray])


def get_input(prompt):
    if sys.version_info.major < 3:
        return raw_input(prompt) # pylint: disable=undefined-variable
    return input(prompt)


debug(sys.version_info.major)


try:
    import dbus
except ImportError:
    if sys.version_info.major == 3:
        missing_dbus()
    if sys.version_info.major < 3:
        try:
            subprocess.call(['python3'] + sys.argv)
        except:
            missing_dbus()
        sys.exit(0)

try:
    from OpenSSL import crypto
except ImportError:
    CRYPTO_AVAILABLE = False


if sys.version_info.major == 3 and sys.version_info.minor >= 7:
    import distro
else:
    import platform


# the function below was partially copied
# from https://ubuntuforums.org/showthread.php?t=1139057
def detect_desktop_environment():
    """
    Detect what desktop type is used. This method is prepared for
    possible future use with password encryption on supported distros
    """
    desktop_environment = 'generic'
    if os.environ.get('KDE_FULL_SESSION') == 'true':
        desktop_environment = 'kde'
    elif os.environ.get('GNOME_DESKTOP_SESSION_ID'):
        desktop_environment = 'gnome'
    else:
        try:
            shell_command = subprocess.Popen(['xprop', '-root',
                                              '_DT_SAVE_MODE'],
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE)
            out, err = shell_command.communicate()
            info = out.decode('utf-8').strip()
        except (OSError, RuntimeError):
            pass
        else:
            if ' = "xfce4"' in info:
                desktop_environment = 'xfce'
    return desktop_environment


def get_system():
    """
    Detect Linux platform. Not used at this stage.
    It is meant to enable password encryption in distros
    that can handle this well.
    """
    if sys.version_info.major == 3 and sys.version_info.minor >= 7:
        system = distro.linux_distribution()
    else:
        system = platform.linux_distribution()
    desktop = detect_desktop_environment()
    return [system[0], system[1], desktop]


def run_installer():
    """
    This is the main installer part. It tests for MN availability
    gets user credentials and starts a proper installer.
    """
    global DEBUG_ON
    global NM_AVAILABLE
    username = ''
    password = ''
    silent = False
    pfx_file = ''
    parser = argparse.ArgumentParser(description='eduroam linux installer.')
    parser.add_argument('--debug', '-d', action='store_true', dest='debug',
                        default=False, help='set debug flag')
    parser.add_argument('--username', '-u', action='store', dest='username',
                        help='set username')
    parser.add_argument('--password', '-p', action='store', dest='password',
                        help='set text_mode flag')
    parser.add_argument('--silent', '-s', action='store_true', dest='silent',
                        help='set silent flag')
    parser.add_argument('--pfxfile', action='store', dest='pfx_file',
                        help='set path to user certificate file')
    args = parser.parse_args()
    if args.debug:
        DEBUG_ON = True
        print("Running debug mode")

    if args.username:
        username = args.username
    if args.password:
        password = args.password
    if args.silent:
        silent = args.silent
    if args.pfx_file:
        pfx_file = args.pfx_file
    debug(get_system())
    debug("Calling InstallerData")
    installer_data = InstallerData(silent=silent, username=username,
                                   password=password, pfx_file=pfx_file)

    # test dbus connection
    if NM_AVAILABLE:
        config_tool = CatNMConfigTool()
        if config_tool.connect_to_nm() is None:
            NM_AVAILABLE = False
    if not NM_AVAILABLE:
        # no dbus so ask if the user will want wpa_supplicant config
        if installer_data.ask(Messages.save_wpa_conf, Messages.cont, 1):
            sys.exit(1)
    installer_data.get_user_cred()
    installer_data.save_ca()
    if NM_AVAILABLE:
        config_tool.add_connections(installer_data)
    else:
        wpa_config = WpaConf()
        wpa_config.create_wpa_conf(Config.ssids, installer_data)
    installer_data.show_info(Messages.installation_finished)


class Messages(object):
    """
    These are initial definitions of messages, but they will be
    overridden with translated strings.
    """
    quit = "Really quit?"
    username_prompt = "enter your userid"
    enter_password = "enter password"
    enter_import_password = "enter your import password"
    incorrect_password = "incorrect password"
    repeat_password = "repeat your password"
    passwords_differ = "passwords do not match"
    installation_finished = "Installation successful"
    cat_dir_exists = "Directory {} exists; some of its files may be " \
        "overwritten."
    cont = "Continue?"
    nm_not_supported = "This NetworkManager version is not supported"
    cert_error = "Certificate file not found, looks like a CAT error"
    unknown_version = "Unknown version"
    dbus_error = "DBus connection problem, a sudo might help"
    yes = "Y"
    nay = "N"
    p12_filter = "personal certificate file (p12 or pfx)"
    all_filter = "All files"
    p12_title = "personal certificate file (p12 or pfx)"
    save_wpa_conf = "NetworkManager configuration failed, " \
        "but we may generate a wpa_supplicant configuration file " \
        "if you wish. Be warned that your connection password will be saved " \
        "in this file as clear text."
    save_wpa_confirm = "Write the file"
    wrongUsernameFormat = "Error: Your username must be of the form " \
        "'xxx@institutionID' e.g. 'john@example.net'!"
    wrong_realm = "Error: your username must be in the form of 'xxx@{}'. " \
        "Please enter the username in the correct format."
    wrong_realm_suffix = "Error: your username must be in the form of " \
        "'xxx@institutionID' and end with '{}'. Please enter the username " \
        "in the correct format."
    user_cert_missing = "personal certificate file not found"
    # "File %s exists; it will be overwritten."
    # "Output written to %s"


class Config(object):
    """
    This is used to prepare settings during installer generation.
    """
    instname = ""
    profilename = ""
    url = ""
    email = ""
    title = "eduroam CAT"
    servers = []
    ssids = []
    del_ssids = []
    eap_outer = ''
    eap_inner = ''
    use_other_tls_id = False
    server_match = ''
    anonymous_identity = ''
    CA = ""
    init_info = ""
    init_confirmation = ""
    tou = ""
    sb_user_file = ""
    verify_user_realm_input = False
    user_realm = ""
    hint_user_input = False


class InstallerData(object):
    """
    General user interaction handling, supports zenity, kdialog and
    standard command-line interface
    """

    def __init__(self, silent=False, username='', password='', pfx_file=''):
        self.graphics = ''
        self.username = username
        self.password = password
        self.silent = silent
        self.pfx_file = pfx_file
        debug("starting constructor")
        if silent:
            self.graphics = 'tty'
        else:
            self.__get_graphics_support()
        self.show_info(Config.init_info.format(Config.instname,
                                               Config.email, Config.url))
        if self.ask(Config.init_confirmation.format(Config.instname,
                                                    Config.profilename),
                    Messages.cont, 1):
            sys.exit(1)
        if Config.tou != '':
            if self.ask(Config.tou, Messages.cont, 1):
                sys.exit(1)
        if os.path.exists(os.environ.get('HOME') + '/.cat_installer'):
            if self.ask(Messages.cat_dir_exists.format(
                    os.environ.get('HOME') + '/.cat_installer'),
                        Messages.cont, 1):
                sys.exit(1)
        else:
            os.mkdir(os.environ.get('HOME') + '/.cat_installer', 0o700)

    def save_ca(self):
        """
        Save CA certificate to .cat_installer directory
        (create directory if needed)
        """
        certfile = os.environ.get('HOME') + '/.cat_installer/ca.pem'
        debug("saving cert")
        with open(certfile, 'w') as cert:
            cert.write(Config.CA + "\n")

    def ask(self, question, prompt='', default=None):
        """
        Propmpt user for a Y/N reply, possibly supplying a default answer
        """
        if self.silent:
            return 0
        if self.graphics == 'tty':
            yes = Messages.yes[:1].upper()
            nay = Messages.nay[:1].upper()
            print("\n-------\n" + question + "\n")
            while True:
                tmp = prompt + " (" + Messages.yes + "/" + Messages.nay + ") "
                if default == 1:
                    tmp += "[" + yes + "]"
                elif default == 0:
                    tmp += "[" + nay + "]"
                inp = get_input(tmp)
                if inp == '':
                    if default == 1:
                        return 0
                    if default == 0:
                        return 1
                i = inp[:1].upper()
                if i == yes:
                    return 0
                if i == nay:
                    return 1
        if self.graphics == "zenity":
            command = ['zenity', '--title=' + Config.title, '--width=500',
                       '--question', '--text=' + question + "\n\n" + prompt]
        elif self.graphics == 'kdialog':
            command = ['kdialog', '--yesno', question + "\n\n" + prompt,
                       '--title=', Config.title]
        returncode = subprocess.call(command, stderr=STDERR_REDIR)
        return returncode

    def show_info(self, data):
        """
        Show a piece of information
        """
        if self.silent:
            return
        if self.graphics == 'tty':
            print(data)
            return
        if self.graphics == "zenity":
            command = ['zenity', '--info', '--width=500', '--text=' + data]
        elif self.graphics == "kdialog":
            command = ['kdialog', '--msgbox', data]
        else:
            sys.exit(1)
        subprocess.call(command, stderr=STDERR_REDIR)

    def confirm_exit(self):
        """
        Confirm exit from installer
        """
        ret = self.ask(Messages.quit)
        if ret == 0:
            sys.exit(1)

    def alert(self, text):
        """Generate alert message"""
        if self.silent:
            return
        if self.graphics == 'tty':
            print(text)
            return
        if self.graphics == 'zenity':
            command = ['zenity', '--warning', '--text=' + text]
        elif self.graphics == "kdialog":
            command = ['kdialog', '--sorry', text]
        else:
            sys.exit(1)
        subprocess.call(command, stderr=STDERR_REDIR)

    def prompt_nonempty_string(self, show, prompt, val=''):
        """
        Prompt user for input
        """
        if self.graphics == 'tty':
            if show == 0:
                while True:
                    inp = str(getpass.getpass(prompt + ": "))
                    output = inp.strip()
                    if output != '':
                        return output
            while True:
                inp = str(get_input(prompt + ": "))
                output = inp.strip()
                if output != '':
                    return output

        if self.graphics == 'zenity':
            if val == '':
                default_val = ''
            else:
                default_val = '--entry-text=' + val
            if show == 0:
                hide_text = '--hide-text'
            else:
                hide_text = ''
            command = ['zenity', '--entry', hide_text, default_val,
                       '--width=500', '--text=' + prompt]
        elif self.graphics == 'kdialog':
            if show == 0:
                hide_text = '--password'
            else:
                hide_text = '--inputbox'
            command = ['kdialog', hide_text, prompt]

        output = ''
        while not output:
            shell_command = subprocess.Popen(command, stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE)
            out, err = shell_command.communicate()
            output = out.decode('utf-8').strip()
            if shell_command.returncode == 1:
                self.confirm_exit()
        return output

    def get_user_cred(self):
        """
        Get user credentials both username/password and personal certificate
        based
        """
        if Config.eap_outer == 'PEAP' or Config.eap_outer == 'TTLS':
            self.__get_username_password()
        if Config.eap_outer == 'TLS':
            self.__get_p12_cred()

    def __get_username_password(self):
        """
        read user password and set the password property
        do nothing if silent mode is set
        """
        password = "a"
        password1 = "b"
        if self.silent:
            return
        if self.username:
            user_prompt = self.username
        elif Config.hint_user_input:
            user_prompt = '@' + Config.user_realm
        else:
            user_prompt = ''
        while True:
            self.username = self.prompt_nonempty_string(
                1, Messages.username_prompt, user_prompt)
            if self.__validate_user_name():
                break
        while password != password1:
            password = self.prompt_nonempty_string(
                0, Messages.enter_password)
            password1 = self.prompt_nonempty_string(
                0, Messages.repeat_password)
            if password != password1:
                self.alert(Messages.passwords_differ)
        self.password = password

    def __get_graphics_support(self):
        if os.environ.get('DISPLAY') is not None:
            shell_command = subprocess.Popen(['which', 'zenity'],
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE)
            shell_command.wait()
            if shell_command.returncode == 0:
                self.graphics = 'zenity'
            else:
                shell_command = subprocess.Popen(['which', 'kdialog'],
                                                 stdout=subprocess.PIPE,
                                                 stderr=subprocess.PIPE)
                shell_command.wait()
                # out, err = shell_command.communicate()
                if shell_command.returncode == 0:
                    self.graphics = 'kdialog'
                else:
                    self.graphics = 'tty'
        else:
            self.graphics = 'tty'

    def __process_p12(self):
        debug('process_p12')
        pfx_file = os.environ['HOME'] + '/.cat_installer/user.p12'
        if CRYPTO_AVAILABLE:
            debug("using crypto")
            try:
                p12 = crypto.load_pkcs12(open(pfx_file, 'rb').read(),
                                         self.password)
            except:
                debug("incorrect password")
                return False
            else:
                if Config.use_other_tls_id:
                    return True
                try:
                    self.username = p12.get_certificate().\
                        get_subject().commonName
                except:
                    self.username = p12.get_certificate().\
                        get_subject().emailAddress
                return True
        else:
            debug("using openssl")
            command = ['openssl', 'pkcs12', '-in', pfx_file, '-passin',
                       'pass:' + self.password, '-nokeys', '-clcerts']
            shell_command = subprocess.Popen(command, stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE)
            out, err = shell_command.communicate()
            if shell_command.returncode != 0:
                return False
            if Config.use_other_tls_id:
                return True
            out_str = out.decode('utf-8').strip()
            subject = re.split(r'\s*[/,]\s*',
                               re.findall(r'subject=/?(.*)$',
                                          out_str, re.MULTILINE)[0])
            cert_prop = {}
            for field in subject:
                if field:
                    cert_field = re.split(r'\s*=\s*', field)
                    cert_prop[cert_field[0].lower()] = cert_field[1]
            if cert_prop['cn'] and re.search(r'@', cert_prop['cn']):
                debug('Using cn: ' + cert_prop['cn'])
                self.username = cert_prop['cn']
            elif cert_prop['emailaddress'] and \
                    re.search(r'@', cert_prop['emailaddress']):
                debug('Using email: ' + cert_prop['emailaddress'])
                self.username = cert_prop['emailaddress']
            else:
                self.username = ''
                self.alert("Unable to extract username "
                           "from the certificate")
            return True

    def __select_p12_file(self):
        """
        prompt user for the PFX file selection
        this method is not being called in the silent mode
        therefore there is no code for this case
        """
        if self.graphics == 'tty':
            my_dir = os.listdir(".")
            p_count = 0
            pfx_file = ''
            for my_file in my_dir:
                if my_file.endswith('.p12') or my_file.endswith('*.pfx') or \
                        my_file.endswith('.P12') or my_file.endswith('*.PFX'):
                    p_count += 1
                    pfx_file = my_file
            prompt = "personal certificate file (p12 or pfx)"
            default = ''
            if p_count == 1:
                default = '[' + pfx_file + ']'

            while True:
                inp = get_input(prompt + default + ": ")
                output = inp.strip()

                if default != '' and output == '':
                    return pfx_file
                default = ''
                if os.path.isfile(output):
                    return output
                print("file not found")

        if self.graphics == 'zenity':
            command = ['zenity', '--file-selection',
                       '--file-filter=' + Messages.p12_filter +
                       ' | *.p12 *.P12 *.pfx *.PFX', '--file-filter=' +
                       Messages.all_filter + ' | *',
                       '--title=' + Messages.p12_title]
            shell_command = subprocess.Popen(command, stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE)
            cert, err = shell_command.communicate()
        if self.graphics == 'kdialog':
            command = ['kdialog', '--getopenfilename',
                       '.', '*.p12 *.P12 *.pfx *.PFX | ' +
                       Messages.p12_filter, '--title', Messages.p12_title]
            shell_command = subprocess.Popen(command, stdout=subprocess.PIPE,
                                             stderr=STDERR_REDIR)
            cert, err = shell_command.communicate()
        return cert.decode('utf-8').strip()

    def __save_sb_pfx(self):
        """write the user PFX file"""
        certfile = os.environ.get('HOME') + '/.cat_installer/user.p12'
        with open(certfile, 'wb') as cert:
            cert.write(base64.b64decode(Config.sb_user_file))

    def __get_p12_cred(self):
        """get the password for the PFX file"""
        if Config.eap_inner == 'SILVERBULLET':
            self.__save_sb_pfx()
        else:
            if self.silent:
                pfx_file = self.pfx_file
            else:
                pfx_file = self.__select_p12_file()
                try:
                    copyfile(pfx_file, os.environ['HOME'] +
                             '/.cat_installer/user.p12')
                except (OSError, RuntimeError):
                    print(Messages.user_cert_missing)
                    sys.exit(1)
        if self.silent:
            username = self.username
            if not self.__process_p12():
                sys.exit(1)
            if username:
                self.username = username
        else:
            while not self.password:
                self.password = self.prompt_nonempty_string(
                    0, Messages.enter_import_password)
                if not self.__process_p12():
                    self.alert(Messages.incorrect_password)
                    self.password = ''
            if not self.username:
                self.username = self.prompt_nonempty_string(
                    1, Messages.username_prompt)

    def __validate_user_name(self):
        # locate the @ character in username
        pos = self.username.find('@')
        debug("@ position: " + str(pos))
        # trailing @
        if pos == len(self.username) - 1:
            debug("username ending with @")
            self.alert(Messages.wrongUsernameFormat)
            return False
        # no @ at all
        if pos == -1:
            if Config.verify_user_realm_input:
                debug("missing realm")
                self.alert(Messages.wrongUsernameFormat)
                return False
            debug("No realm, but possibly correct")
            return True
        # @ at the beginning
        if pos == 0:
            debug("missing user part")
            self.alert(Messages.wrongUsernameFormat)
            return False
        pos += 1
        if Config.verify_user_realm_input:
            if Config.hint_user_input:
                if self.username.endswith('@' + Config.user_realm, pos-1):
                    debug("realm equal to the expected value")
                    return True
                debug("incorrect realm; expected:" + Config.user_realm)
                self.alert(Messages.wrong_realm.format(Config.user_realm))
                return False
            if self.username.endswith(Config.user_realm, pos):
                debug("realm ends with expected suffix")
                return True
            debug("realm suffix error; expected: " + Config.user_realm)
            self.alert(Messages.wrong_realm_suffix.format(
                Config.user_realm))
            return False
        pos1 = self.username.find('@', pos)
        if pos1 > -1:
            debug("second @ character found")
            self.alert(Messages.wrongUsernameFormat)
            return False
        pos1 = self.username.find('.', pos)
        if pos1 == pos:
            debug("a dot immediately after the @ character")
            self.alert(Messages.wrongUsernameFormat)
            return False
        debug("all passed")
        return True


class WpaConf(object):
    """
    Prepare and save wpa_supplicant config file
    """
    def __prepare_network_block(self, ssid, user_data):
        out = """network={
        ssid=\"""" + ssid + """\"
        key_mgmt=WPA-EAP
        pairwise=CCMP
        group=CCMP TKIP
        eap=""" + Config.eap_outer + """
        ca_cert=\"""" + os.environ.get('HOME') + """/.cat_installer/ca.pem\"
        identity=\"""" + user_data.username + """\"
        altsubject_match=\"""" + ";".join(Config.servers) + """\"
        phase2=\"auth=""" + Config.eap_inner + """\"
        password=\"""" + user_data.password + """\"
        anonymous_identity=\"""" + Config.anonymous_identity + """\"
}
    """
        return out

    def create_wpa_conf(self, ssids, user_data):
        """Create and save the wpa_supplicant config file"""
        wpa_conf = os.environ.get('HOME') + \
            '/.cat_installer/cat_installer.conf'
        with open(wpa_conf, 'w') as conf:
            for ssid in ssids:
                net = self.__prepare_network_block(ssid, user_data)
                conf.write(net)


class CatNMConfigTool(object):
    """
    Prepare and save NetworkManager configuration
    """
    def __init__(self):
        self.cacert_file = None
        self.settings_service_name = None
        self.connection_interface_name = None
        self.system_service_name = None
        self.nm_version = None
        self.pfx_file = None
        self.settings = None
        self.user_data = None
        self.bus = None

    def connect_to_nm(self):
        """
        connect to DBus
        """
        try:
            self.bus = dbus.SystemBus()
        except dbus.exceptions.DBusException:
            print("Can't connect to DBus")
            return None
        # main service name
        self.system_service_name = "org.freedesktop.NetworkManager"
        # check NM version
        self.__check_nm_version()
        debug("NM version: " + self.nm_version)
        if self.nm_version == "0.9" or self.nm_version == "1.0":
            self.settings_service_name = self.system_service_name
            self.connection_interface_name = \
                "org.freedesktop.NetworkManager.Settings.Connection"
            # settings proxy
            sysproxy = self.bus.get_object(
                self.settings_service_name,
                "/org/freedesktop/NetworkManager/Settings")
            # settings interface
            self.settings = dbus.Interface(sysproxy, "org.freedesktop."
                                           "NetworkManager.Settings")
        elif self.nm_version == "0.8":
            self.settings_service_name = "org.freedesktop.NetworkManager"
            self.connection_interface_name = "org.freedesktop.NetworkMana" \
                                             "gerSettings.Connection"
            # settings proxy
            sysproxy = self.bus.get_object(
                self.settings_service_name,
                "/org/freedesktop/NetworkManagerSettings")
            # settings intrface
            self.settings = dbus.Interface(
                sysproxy, "org.freedesktop.NetworkManagerSettings")
        else:
            print(Messages.nm_not_supported)
            return None
        debug("NM connection worked")
        return True

    def __check_opts(self):
        """
        set certificate files paths and test for existence of the CA cert
        """
        self.cacert_file = os.environ['HOME'] + '/.cat_installer/ca.pem'
        self.pfx_file = os.environ['HOME'] + '/.cat_installer/user.p12'
        if not os.path.isfile(self.cacert_file):
            print(Messages.cert_error)
            sys.exit(2)

    def __check_nm_version(self):
        """
        Get the NetworkManager version
        """
        try:
            proxy = self.bus.get_object(
                self.system_service_name, "/org/freedesktop/NetworkManager")
            props = dbus.Interface(proxy, "org.freedesktop.DBus.Properties")
            version = props.Get("org.freedesktop.NetworkManager", "Version")
        except dbus.exceptions.DBusException:
            version = ""
        if re.match(r'^1\.', version):
            self.nm_version = "1.0"
            return
        if re.match(r'^0\.9', version):
            self.nm_version = "0.9"
            return
        if re.match(r'^0\.8', version):
            self.nm_version = "0.8"
            return
        self.nm_version = Messages.unknown_version

    def __delete_existing_connection(self, ssid):
        """
        checks and deletes earlier connection
        """
        try:
            conns = self.settings.ListConnections()
        except dbus.exceptions.DBusException:
            print(Messages.dbus_error)
            exit(3)
        for each in conns:
            con_proxy = self.bus.get_object(self.system_service_name, each)
            connection = dbus.Interface(
                con_proxy,
                "org.freedesktop.NetworkManager.Settings.Connection")
            try:
                connection_settings = connection.GetSettings()
                if connection_settings['connection']['type'] == '802-11-' \
                                                                'wireless':
                    conn_ssid = byte_to_string(
                        connection_settings['802-11-wireless']['ssid'])
                    if conn_ssid == ssid:
                        debug("deleting connection: " + conn_ssid)
                        connection.Delete()
            except dbus.exceptions.DBusException:
                pass

    def __add_connection(self, ssid):
        debug("Adding connection: " + ssid)
        server_alt_subject_name_list = dbus.Array(Config.servers)
        server_name = Config.server_match
        if self.nm_version == "0.9" or self.nm_version == "1.0":
            match_key = 'altsubject-matches'
            match_value = server_alt_subject_name_list
        else:
            match_key = 'subject-match'
            match_value = server_name
        s_8021x_data = {
            'eap': [Config.eap_outer.lower()],
            'identity': self.user_data.username,
            'ca-cert': dbus.ByteArray(
                "file://{0}\0".format(self.cacert_file).encode('utf8')),
            match_key: match_value}
        if Config.eap_outer == 'PEAP' or Config.eap_outer == 'TTLS':
            s_8021x_data['password'] = self.user_data.password
            s_8021x_data['phase2-auth'] = Config.eap_inner.lower()
            if Config.anonymous_identity != '':
                s_8021x_data['anonymous-identity'] = Config.anonymous_identity
            s_8021x_data['password-flags'] = 0
        if Config.eap_outer == 'TLS':
            s_8021x_data['client-cert'] = dbus.ByteArray(
                "file://{0}\0".format(self.pfx_file).encode('utf8'))
            s_8021x_data['private-key'] = dbus.ByteArray(
                "file://{0}\0".format(self.pfx_file).encode('utf8'))
            s_8021x_data['private-key-password'] = self.user_data.password
            s_8021x_data['private-key-password-flags'] = 0
        s_con = dbus.Dictionary({
            'type': '802-11-wireless',
            'uuid': str(uuid.uuid4()),
            'permissions': ['user:' +
                            os.environ.get('USER')],
            'id': ssid
            })
        s_wifi = dbus.Dictionary({
            'ssid': dbus.ByteArray(ssid.encode('utf8')),
            'security': '802-11-wireless-security'
            })
        s_wsec = dbus.Dictionary({
            'key-mgmt': 'wpa-eap',
            'proto': ['rsn'],
            'pairwise': ['ccmp'],
            'group': ['ccmp', 'tkip']
            })
        s_8021x = dbus.Dictionary(s_8021x_data)
        s_ip4 = dbus.Dictionary({'method': 'auto'})
        s_ip6 = dbus.Dictionary({'method': 'auto'})
        con = dbus.Dictionary({
            'connection': s_con,
            '802-11-wireless': s_wifi,
            '802-11-wireless-security': s_wsec,
            '802-1x': s_8021x,
            'ipv4': s_ip4,
            'ipv6': s_ip6
            })
        self.settings.AddConnection(con)

    def add_connections(self, user_data):
        """Delete and then add connections to the system"""
        self.__check_opts()
        self.user_data = user_data
        for ssid in Config.ssids:
            self.__delete_existing_connection(ssid)
            self.__add_connection(ssid)
        for ssid in Config.del_ssids:
            self.__delete_existing_connection(ssid)


Messages.quit = "Really quit?"
Messages.username_prompt = "enter your userid"
Messages.enter_password = "enter password"
Messages.enter_import_password = "enter your import password"
Messages.incorrect_password = "incorrect password"
Messages.repeat_password = "repeat your password"
Messages.passwords_differ = "passwords do not match"
Messages.installation_finished = "Installation successful"
Messages.cat_dir_exisits = "Directory {} exists; some of its files may " \
    "be overwritten."
Messages.cont = "Continue?"
Messages.nm_not_supported = "This NetworkManager version is not " \
    "supported"
Messages.cert_error = "Certificate file not found, looks like a CAT " \
    "error"
Messages.unknown_version = "Unknown version"
Messages.dbus_error = "DBus connection problem, a sudo might help"
Messages.yes = "Y"
Messages.no = "N"
Messages.p12_filter = "personal certificate file (p12 or pfx)"
Messages.all_filter = "All files"
Messages.p12_title = "personal certificate file (p12 or pfx)"
Messages.save_wpa_conf = "NetworkManager configuration failed, but we " \
    "may generate a wpa_supplicant configuration file if you wish. Be " \
    "warned that your connection password will be saved in this file as " \
    "clear text."
Messages.save_wpa_confirm = "Write the file"
Messages.wrongUsernameFormat = "Error: Your username must be of the " \
    "form 'xxx@institutionID' e.g. 'john@example.net'!"
Messages.wrong_realm = "Error: your username must be in the form of " \
    "'xxx@{}'. Please enter the username in the correct format."
Messages.wrong_realm_suffix = "Error: your username must be in the " \
    "form of 'xxx@institutionID' and end with '{}'. Please enter the " \
    "username in the correct format."
Messages.user_cert_missing = "personal certificate file not found"
Config.instname = "University of Tasmania"
Config.profilename = "Eduroam"
Config.url = "https://servicedesk.its.utas.edu.au/"
Config.email = "service.desk@utas.edu.au"
Config.title = "eduroam CAT"
Config.server_match = "its.utas.edu.au"
Config.eap_outer = "PEAP"
Config.eap_inner = "MSCHAPV2"
Config.init_info = "This installer has been prepared for {0}\n\nMore " \
    "information and comments:\n\nEMAIL: {1}\nWWW: {2}\n\nInstaller created " \
    "with software from the GEANT project."
Config.init_confirmation = "This installer will only work properly if " \
    "you are a member of {0}."
Config.user_realm = "utas.edu.au"
Config.ssids = ['eduroam']
Config.del_ssids = []
Config.servers = ['DNS:clearpass-1.its.utas.edu.au', 'DNS:clearpass-2.its.utas.edu.au', 'DNS:clearpass.its.utas.edu.au', 'DNS:radius.its.utas.edu.au']
Config.use_other_tls_id = False
Config.tou = ""
Config.CA = """-----BEGIN CERTIFICATE-----
MIIFVDCCAzygAwIBAgIQZR6Qoh6s1KpHk2KvH96jXDANBgkqhkiG9w0BAQsFADAX
MRUwEwYDVQQDEwxVVEFTIFJvb3QgQ0EwHhcNMTYwODE3MjM0NTUzWhcNMjgwODE3
MjM1NTUwWjAXMRUwEwYDVQQDEwxVVEFTIFJvb3QgQ0EwggIiMA0GCSqGSIb3DQEB
AQUAA4ICDwAwggIKAoICAQCh4E4tDjUw618/2oLd2WyFSsMdQFnKH5FwBKOJBmL5
p8RUpEYC1CmlwYZivp7tYovK9dXYOHsr1ixO2UUVSdF7to5hog9ZYLqvCrnNueST
0S/oJguPsA0T1K4mKATe3DF5/PIOmjKZl58bHmMvCvKzUBGvoVQYRL9YVZqfAnc2
03nZwYzewKGVKuEnYUkhdHN9Pq86RwbfOBU3GnGxRdggfY2bfJBwKIPMXnx5DKgl
1lNzGshN8CpFdLd6+63qb0igsjkbn6kqeMZ2NVmn7cZtKTinlKyjG2Sv7Mh1/TQM
Y3aIzhwUNlrOEtWD5SIrbq+DiKfSh6iWa3N1RDpKIbEErwm9IArHLbNrvHSHRgv1
Kz5vD8Z7nHMUFfOMj6EIeyPn+WR961OIWKaJwybymIhuQZA/07AFJkSPwODcmepj
WXux2Q8khdzoz7wTicCzVjPOmkMrwDqr1rrpgzfbzUT0q7IyMJiVtNOlA0YwRRLw
FbHQwXi0O0BoFixZm2QJHSVLQGVermsvddhCzBq4FN9GSSOPNUBfONgRSeBBhnYR
P2zYeEcUIgA6JBiC2zm8ZjPViuG5nE7/IFXcI68LpioFLQJww+9/odVfw0fMxBcw
acJtPS9gJzye8GmY39Afrw/ypq6740wXvuVcu/jxEnu5No6aJk8HNy/oEz0GT5p5
8QIDAQABo4GbMIGYMAsGA1UdDwQEAwIBhjASBgNVHRMBAf8ECDAGAQH/AgEBMB0G
A1UdDgQWBBQDWUMSAPn66P97HS/u9UMGsoaUqTAQBgkrBgEEAYI3FQEEAwIBADBE
BgNVHSAEPTA7MDkGDCkBAQEBAoEDgXKCYTApMCcGCCsGAQUFBwIBFhtodHRwOi8v
cGtpLnV0YXMuZWR1LmF1L2NwcwAwDQYJKoZIhvcNAQELBQADggIBAG80Gkq91REl
8cfP/8AyyU101V+vHwyLnyEsISUJP19q8VVGC5ovOg2BzVVi8nTaIwByMOdAe2bC
8uCvfzRCOmaROseqH/PJiGhidhcWDI3V7rys9QV+13RQEiXpVTmix806903+oW6a
7G4KXb+/ctqNTuUJtPh54iM1KR8//Y9c3MPei1Fa8xBcWjHfCREpQ0T5k6NOben4
6V64ndvZmKZfJd5ZKElsqUdUjoO5IG2nJOGwSXM5f7IfgigoOAnk/+UXfscEdzqV
2yYX1j0u/b18MrZSwNyWQCk2FG5ja1sxISrRGSQq0EXQAHxwIRUYLbDxU8ZX86Zy
dON4xC8jQH4STPsYeGqqq9CqEnD5JP7uRfClHrg4y3ZosSzWmYQqEHYJgu6HwbHb
svhqLh1l7uBTw83N5YQIMHJ1icRVh9rDmrR2EQr52Tr9sAvh8Cvz6h3GO1hiHZ+Y
RFOrwIRaus/aU8PcJ3+7Q226VG2TuIvi9vy4h1O/fjQymo5SFpUdhXdxDJ/gd3e+
EU96O+8Vc8nnqnPQGgffx7TXHyEdan2YCnA9vTn8zt/WZG3DWSc92OLeaN8shVTe
SHhL3U7b1OdQ4lXlUG/YLVW9T3I1DR/Iit4o4nSErfrSsJiZ+EFUx0UsZ2TeFT0q
FMPakIyhBf2ytC7bg2ilYQhtpwI51bOY
-----END CERTIFICATE-----
-----BEGIN CERTIFICATE-----
MIIFYDCCA0igAwIBAgIURFc0JFuBiZs18s64KztbpybwdSgwDQYJKoZIhvcNAQEL
BQAwSDELMAkGA1UEBhMCQk0xGTAXBgNVBAoTEFF1b1ZhZGlzIExpbWl0ZWQxHjAc
BgNVBAMTFVF1b1ZhZGlzIFJvb3QgQ0EgMiBHMzAeFw0xMjAxMTIxODU5MzJaFw00
MjAxMTIxODU5MzJaMEgxCzAJBgNVBAYTAkJNMRkwFwYDVQQKExBRdW9WYWRpcyBM
aW1pdGVkMR4wHAYDVQQDExVRdW9WYWRpcyBSb290IENBIDIgRzMwggIiMA0GCSqG
SIb3DQEBAQUAA4ICDwAwggIKAoICAQChriWyARjcV4g/Ruv5r+LrI3HimtFhZiFf
qq8nUeVuGxbULX1QsFN3vXg6YOJkApt8hpvWGo6t/x8Vf9WVHhLL5hSEBMHfNrMW
n4rjyduYNM7YMxcoRvynyfDStNVNCXJJ+fKH46nafaF9a7I6JaltUkSs+L5u+9ym
c5GQYaYDFCDy54ejiK2toIz/pgslUiXnFgHVy7g1gQyjO/Dh4fxaXc6AcW34Sas+
O7q414AB+6XrW7PFXmAqMaCvN+ggOp+oMiwMzAkd056OXbxMmO7FGmh77FOm6RQ1
o9/NgJ8MSPsc9PG/Srj61YxxSscfrf5BmrODXfKEVu+lV0POKa2Mq1W/xPtbAd0j
IaFYAI7D0GoT7RPjEiuA3GfmlbLNHiJuKvhB1PLKFAeNilUSxmn1uIZoL1NesNKq
IcGY5jDjZ1XHm26sGahVpkUG0CM62+tlXSoREfA7T8pt9DTEceT/AFr2XK4jYIVz
8eQQsSWu1ZK7E8EM4DnatDlXtas1qnIhO4M15zHfeiFuuDIIfR0ykRVKYnLP43eh
vNURG3YBZwjgQQvD6xVu+KQZ2aKrr+InUlYrAoosFCT5v0ICvybIxo/gbjh9Uy3l
7ZizlWNof/k19N+IxWA1ksB8aRxhlRbQ694Lrz4EEEVlWFA4r0jyWbYW8jwNkALG
cC4BrTwV1wIDAQABo0IwQDAPBgNVHRMBAf8EBTADAQH/MA4GA1UdDwEB/wQEAwIB
BjAdBgNVHQ4EFgQU7edvdlq/YOxJW8ald7tyFnGbxD0wDQYJKoZIhvcNAQELBQAD
ggIBAJHfgD9DCX5xwvfrs4iP4VGyvD11+ShdyLyZm3tdquXK4Qr36LLTn91nMX66
AarHakE7kNQIXLJgapDwyM4DYvmL7ftuKtwGTTwpD4kWilhMSA/ohGHqPHKmd+RC
roijQ1h5fq7KpVMNqT1wvSAZYaRsOPxDMuHBR//47PERIjKWnML2W2mWeyAMQ0Ga
W/ZZGYjeVYg3UQt4XAoeo0L9x52ID8DyeAIkVJOviYeIyUqAHerQbj5hLja7NQ4n
lv1mNDthcnPxFlxHBlRJAHpYErAK74X9sbgzdWqTHBLmYF5vHX/JHyPLhGGfHoJE
+V+tYlUkmlKY7VHnoX6XOuYvHxHaU4AshZ6rNRDbIl9qxV6XU/IyAgkwo1jwDQHV
csaxfGl7w/U2Rcxhbl5MlMVerugOXou/983g7aEOGzPuVBj+D77vfoRrQ+NwmNtd
dbINWQeFFSM51vHfqSYP1kjHs6Yi9TM3WpVHn3u6GBVv/9YUZINJ0gpnIdsPNWNg
KCLjsZWDzYWm3S8P52dSbrsvhXz1SnPnxT7AvSESBT/8twNJAlvIJebiVDj1eYeM
HVOyToV7BjjHLPj4sHKNJeV3UvQDHEimUF+IIDBu8oJDqz2XhOdT+yHBTw8imoa4
WSr2Rz0ZiC3oheGe7IUIarFsNMkd7EgrO3jtZsSOeWmD3n+M
-----END CERTIFICATE-----
-----BEGIN CERTIFICATE-----
MIIGFzCCA/+gAwIBAgIUftbnnMmtgcTIGT75XUQodw40ExcwDQYJKoZIhvcNAQEL
BQAwSDELMAkGA1UEBhMCQk0xGTAXBgNVBAoTEFF1b1ZhZGlzIExpbWl0ZWQxHjAc
BgNVBAMTFVF1b1ZhZGlzIFJvb3QgQ0EgMiBHMzAeFw0xMjExMDYxNDUwMThaFw0y
MjExMDYxNDUwMThaME0xCzAJBgNVBAYTAkJNMRkwFwYDVQQKExBRdW9WYWRpcyBM
aW1pdGVkMSMwIQYDVQQDExpRdW9WYWRpcyBHbG9iYWwgU1NMIElDQSBHMzCCAiIw
DQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBANf8Od17be6c6lTGJDhEXpmkTs4y
Q39Rr5VJyBeWCg06nSS71s6xF3sZvKcV0MbXlXCYM2ZX7cNTbJ81gs7uDsKFp+vK
EymiKyEiI2SImOtECNnSg+RVR4np/xz/UlC0yFUisH75cZsJ8T1pkGMfiEouR0EM
7O0uFgoboRfUP582TTWy0F7ynSA6YfGKnKj0OFwZJmGHVkLs1VevWjhj3R1fsPan
H05P5moePFnpQdj1FofoSxUHZ0c7VB+sUimboHm/uHNY1LOsk77qiSuVC5/yrdg3
2EEfP/mxJYT4r/5UiD7VahySzeZHzZ2OibQm2AfgfMN3l57lCM3/WPQBhMAPS1jz
kE+7MjajM2f0aZctimW4Hasrj8AQnfAdHqZehbhtXaAlffNEzCdpNK584oCTVR7N
UR9iZFx83ruTqpo+GcLP/iSYqhM4g7fy45sNhU+IS+ca03zbxTl3TTlkofXunI5B
xxE30eGSQpDZ5+iUJcEOAuVKrlYocFbB3KF45hwcbzPWQ1DcO2jFAapOtQzeS+MZ
yZzT2YseJ8hQHKu8YrXZWwKaNfyl8kFkHUBDICowNEoZvBwRCQp8sgqL6YRZy0uD
JGxmnC2e0BVKSjcIvmq/CRWH7yiTk9eWm73xrsg9iIyD/kwJEnLyIk8tR5V8p/hc
1H2AjDrZH12PsZ45AgMBAAGjgfMwgfAwEgYDVR0TAQH/BAgwBgEB/wIBATARBgNV
HSAECjAIMAYGBFUdIAAwOgYIKwYBBQUHAQEELjAsMCoGCCsGAQUFBzABhh5odHRw
Oi8vb2NzcC5xdW92YWRpc2dsb2JhbC5jb20wDgYDVR0PAQH/BAQDAgEGMB8GA1Ud
IwQYMBaAFO3nb3Zav2DsSVvGpXe7chZxm8Q9MDsGA1UdHwQ0MDIwMKAuoCyGKmh0
dHA6Ly9jcmwucXVvdmFkaXNnbG9iYWwuY29tL3F2cmNhMmczLmNybDAdBgNVHQ4E
FgQUsxKJtalLNbwVAPCA6dh4h/ETfHYwDQYJKoZIhvcNAQELBQADggIBAFGm1Fqp
RMiKr7a6h707M+km36PVXZnX1NZocCn36MrfRvphotbOCDm+GmRkar9ZMGhc8c/A
Vn7JSCjwF9jNOFIOUyNLq0w4luk+Pt2YFDbgF8IDdx53xIo8Gv05e9xpTvQYaIto
qeHbQjGXfSGc91olfX6JUwZlxxbhdJH+rxTFAg0jcbqToJoScWTfXSr1QRcNbSTs
Y4CPG6oULsnhVvrzgldGSK+DxFi2OKcDsOKkV7W4IGg8Do2L/M588AfBnV8ERzpl
qgMBBQxC2+0N6RdFHbmZt0HQE/NIg1s0xcjGx1XW3YTOfje31rmAXKHOehm4Bu48
gr8gePq5cdQ2W9tA0Dnytb9wzH2SyPPIXRI7yNxaX9H8wYeDeeiKSSmQtfh1v5cV
7RXvm8F6hLJkkco/HOW3dAUwZFcKsUH+1eUJKLN18eDGwB8yGawjHvOKqcfg5Lf/
TvC7hgcx7pDYaCCaqHaekgUwXbB2Enzqr1fdwoU1c01W5YuQAtAx5wk1bf34Yq/J
ph7wNXGvo88N0/EfP9AdVGmJzy7VuRXeVAOyjKAIeADMlwpjBRhcbs9m3dkqvoMb
SXKJxv/hFmNgEOvOlaFsXX1dbKg1v+C1AzKAFdiuAIa62JzASiEhigqNSdqdTsOh
8W8hdONuKKpe9zKedhBFAvuxhDgKmnySglYc
-----END CERTIFICATE-----
-----BEGIN CERTIFICATE-----
MIIHmzCCBYOgAwIBAgITIgAAAAJ7VkqfCeML0QAAAAAAAjANBgkqhkiG9w0BAQsF
ADAXMRUwEwYDVQQDEwxVVEFTIFJvb3QgQ0EwHhcNMTYwODE4MDA0NjAxWhcNMjIw
ODE4MDA1NjAxWjBjMRgwFgYKCZImiZPyLGQBGRYIaW50ZXJuYWwxEjAQBgoJkiaJ
k/IsZAEZFgJhZDEUMBIGCgmSJomT8ixkARkWBHV0YXMxHTAbBgNVBAMTFFVUQVMg
RU5URVJQUklTRSBDQSAxMIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEA
oYaj7WsBKvkSnbzqAwGkrqbWTVLkbRawN4PWJfO4KWCHHZlPsXbxH4q4c5vpDwoS
pyCSKuKmj3w4hhvXDO2M3MiYNBxb11/E23W/FpAWuiuRLdK4fRRAtveGP/wt+oyo
5w+nqYa6QBOHSalEkT9YOQWOHXb6dmtYtQrsQGQtRB18fJnZ7XehPV4Jpnk0Kvb7
MXXTJ27mahUmgfmeWOWXmAMLusM1j6BC9t023FBas6s38Q6GOS4Cn58VsBLkCzm+
lEWhNZAsmpEjw4SuGR8D/yx9qb8R1gmW6nCfENC5j+k5cOdkm1zH7O5x+17lMJmK
zaOpIWbQChGFGLaUNe1GIpbZl6UoQyBYjqO15LunwJgRWem8O72LRS9c14Osmod+
EiBOsmf5YQIAKLVEmgc7dGF37g7FP0bWRP1yog8c8sLlwOdcpOHhSrZ9IlzS28h9
5o6s6VQN2eJIUVQYbpf7BOqe0CfIBPCB+Slp+ZWvRiAO/rUOtnL2MJddz/w91YtN
IGC0jIghT4uLwXoqt1tb1l1fL6DQO4DXJBlqIfe+CqCFEH98bECxk1n0NcxG4NSh
WPjKe0KZrTvxHUFjBGn1SwURhpSr/s8RDcSr9aUWdYYA+pDNxKTwcCi2MXPAjajz
vzW/OL/uLDR6+fHPzFcVdADb7+xfwor3GlbLMSfg+jsCAwEAAaOCApIwggKOMBAG
CSsGAQQBgjcVAQQDAgEAMB0GA1UdDgQWBBSwKjaxmLDhtydjuivwU+e+j1zBVTAZ
BgkrBgEEAYI3FAIEDB4KAFMAdQBiAEMAQTALBgNVHQ8EBAMCAYYwEgYDVR0TAQH/
BAgwBgEB/wIBADAfBgNVHSMEGDAWgBQDWUMSAPn66P97HS/u9UMGsoaUqTCB/gYD
VR0fBIH2MIHzMIHwoIHtoIHqhoG2bGRhcDovLy9DTj1VVEFTJTIwUm9vdCUyMENB
LENOPVJvb3RDQSxDTj1DRFAsQ049UHVibGljJTIwS2V5JTIwU2VydmljZXMsQ049
U2VydmljZXMsQ049Q29uZmlndXJhdGlvbixEQz1BRCxEQz1JTlRFUk5BTD9jZXJ0
aWZpY2F0ZVJldm9jYXRpb25MaXN0P2Jhc2U/b2JqZWN0Q2xhc3M9Y1JMRGlzdHJp
YnV0aW9uUG9pbnSGL2h0dHA6Ly9wa2kudXRhcy5lZHUuYXUvY2RwL1VUQVMlMjBS
b290JTIwQ0EuY3JsMIH8BggrBgEFBQcBAQSB7zCB7DCBrwYIKwYBBQUHMAKGgaJs
ZGFwOi8vL0NOPVVUQVMlMjBSb290JTIwQ0EsQ049QUlBLENOPVB1YmxpYyUyMEtl
eSUyMFNlcnZpY2VzLENOPVNlcnZpY2VzLENOPUNvbmZpZ3VyYXRpb24sREM9QUQs
REM9SU5URVJOQUw/Y0FDZXJ0aWZpY2F0ZT9iYXNlP29iamVjdENsYXNzPWNlcnRp
ZmljYXRpb25BdXRob3JpdHkwOAYIKwYBBQUHMAKGLCBodHRwOi8vcGtpLnV0YXMu
ZWR1LmF1L2FpYS9VVEFTIFJvb3QgQ0EuY3J0MA0GCSqGSIb3DQEBCwUAA4ICAQCN
PiGVFQ6l6wUx79zJPoLpKZ97x/n9iCIn+gZSrHdjj7sMti5UYxb0K/6BspBRWfFS
BRRa3DpImOLgKALHwnt8aFuf+0O9N9GECf1Ny2BQAOW1aGys+kzf/CjmURAOVhMV
ylar83pMDI6soi7T/+CYkk3Sy74v2t4Hdg4x0NcssHz9HPwfDX3xdzxmZ4fz4UPs
5hd4ychFyo4Pd8uXHrNFSg8XVDU3WJ90YVO/QaJbtKGrI099RFQtfwyEXTiepBTG
Mel+wQiPOyr5ywBvQpQvcQt5ArgMTXRQ5pnNDTKr5XyZuJTSKysmAMeV7oXujUzf
qeoFwe47dezlU95q293o9YV4EPtvosLIgrZIyxVhT9X6ecG6C/sSolcyLjhhFH3t
FwJJSRwQ0stf4woQ/0GJLZ9i+BExYrnOrqoxQkmEZkl3Dv7+RASYT+nwEAfF5peI
vXiiOxmGaySl0yaudJ+6JGv5vnmvWHL/Upkn6U/S484d14YaO3zDcjCsS3ZA4ct4
bHa+LDp2K8/4JNVH+buFzhCSjxJot3z0txvUwSN2FEB6OkxFBfMQR/KJkmxui4RX
EYJDrdjtXaqXP/nRF291zwMaKOaqNYrTbiJ28SuaduJDDc+aXL22vFw3Um6uJ/td
61kO6KwjX5bGofl4NM7xJwMsZGrIzDGS7zPXtSOApg==
-----END CERTIFICATE-----
-----BEGIN CERTIFICATE-----
MIIHmzCCBYOgAwIBAgITIgAAAAPBaqN+njhQuwAAAAAAAzANBgkqhkiG9w0BAQsF
ADAXMRUwEwYDVQQDEwxVVEFTIFJvb3QgQ0EwHhcNMTYwODE4MDEzODQ5WhcNMjIw
ODE4MDE0ODQ5WjBjMRgwFgYKCZImiZPyLGQBGRYIaW50ZXJuYWwxEjAQBgoJkiaJ
k/IsZAEZFgJhZDEUMBIGCgmSJomT8ixkARkWBHV0YXMxHTAbBgNVBAMTFFVUQVMg
RU5URVJQUklTRSBDQSAyMIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEA
nYYLvCjHlY6DEx6WI7YhKB/CIJiBMYNrAZct6aOJjxSbDzRUUtJvInamZlv4Ikhw
i/QW5IORthF2qYuusS+aGnBQYfERkLpFTGi19DSIX7EcvfzTO3E73I0l5C0FxveR
LIJlKfwwsSwDmNdwQHAQwrGzgu711cbnWouusg9gAurmI68TFwIV1LtyYjwWnJgw
NgT43XGEFuQih2GP833jv05mJcTBW2Qagi6hnl6J/34jycyl1nr873kg5gbh+KMJ
vGEyXKq62Rui6OUZ1E1YNDsNbXX9AzPAgNbL7SXmEQhZpK/lsTrUsu7QJGpqgziw
qBap0p0kEExcsv2SNZ87+PxOumwKkyqgjzzhaaO4aKgZ+HImSfi7wrho+NJial3S
JNONS1Z2kxVkeMQDtXfH06p2JVGH0UIbpBcABFMyBWuS0EpWQ7j6LmSm/xwT1015
eR2ctYWbHVLv6TIVqpGAmWRXvuIh0omAnPWEndB/kjeKHmj1viIM+UERJR/hvfE+
0slIZlmtyzOTHlsxPM645whW2byiQqhY05NZybZ1hwyVS4MYEqHOw73+Gqe5vpXn
c6U/WPevnX083mQsAn+PyMeMQGg/puT60pN0E1LZlTc4CA+3DpigDGUZU6oZsoGO
fZiX+KYq4NLyeiaRBTTG0dc3PGNt+bfnhFWWXCWvOqcCAwEAAaOCApIwggKOMBAG
CSsGAQQBgjcVAQQDAgEAMB0GA1UdDgQWBBRgIdXw+goBvKeAKjva0x/88abOLDAZ
BgkrBgEEAYI3FAIEDB4KAFMAdQBiAEMAQTALBgNVHQ8EBAMCAYYwEgYDVR0TAQH/
BAgwBgEB/wIBADAfBgNVHSMEGDAWgBQDWUMSAPn66P97HS/u9UMGsoaUqTCB/gYD
VR0fBIH2MIHzMIHwoIHtoIHqhoG2bGRhcDovLy9DTj1VVEFTJTIwUm9vdCUyMENB
LENOPVJvb3RDQSxDTj1DRFAsQ049UHVibGljJTIwS2V5JTIwU2VydmljZXMsQ049
U2VydmljZXMsQ049Q29uZmlndXJhdGlvbixEQz1BRCxEQz1JTlRFUk5BTD9jZXJ0
aWZpY2F0ZVJldm9jYXRpb25MaXN0P2Jhc2U/b2JqZWN0Q2xhc3M9Y1JMRGlzdHJp
YnV0aW9uUG9pbnSGL2h0dHA6Ly9wa2kudXRhcy5lZHUuYXUvY2RwL1VUQVMlMjBS
b290JTIwQ0EuY3JsMIH8BggrBgEFBQcBAQSB7zCB7DCBrwYIKwYBBQUHMAKGgaJs
ZGFwOi8vL0NOPVVUQVMlMjBSb290JTIwQ0EsQ049QUlBLENOPVB1YmxpYyUyMEtl
eSUyMFNlcnZpY2VzLENOPVNlcnZpY2VzLENOPUNvbmZpZ3VyYXRpb24sREM9QUQs
REM9SU5URVJOQUw/Y0FDZXJ0aWZpY2F0ZT9iYXNlP29iamVjdENsYXNzPWNlcnRp
ZmljYXRpb25BdXRob3JpdHkwOAYIKwYBBQUHMAKGLCBodHRwOi8vcGtpLnV0YXMu
ZWR1LmF1L2FpYS9VVEFTIFJvb3QgQ0EuY3J0MA0GCSqGSIb3DQEBCwUAA4ICAQBU
JFnc0777fyCvIDdqS+tZg8phpP/EU4zbPF6MMPykqOoiqJdXeGV/9u0uEPRp8+jX
+OqamVV7daHgx6htgF8ASY57iA1z1pbUG2n1f08lqDkxhlnAkkBTaZeYHV3Q1Shb
n+uRBb2DTdFRRzA3As59bMPEC1wUjNxu1lfq3bHMnnjmwUIM4ajhpIxQxjLd9GpU
tT4wmTV7aGI8sRxDa7/KRm2Sftl01VXr52/FLuryquGnvmbJuBDzum1tQCi0cwNh
Ys0uOal5kRTGMjrE9lF7gLTla+Sg23QHE5DgYMPD391QWQd9tSDGItcITCi55dXE
uzw/qMcLuu7skRvlqjLVHyxNO16DSuesIJO1Jp66mkpQhNNk5a395rOTU3FZABd2
2BxaetQDAWAfHtnIPeDZ5mXgvTMh2FP+plY5MMj+Z6SO4XvEGTJvldLP3beSRGAu
ETideQ1Ab5zaZQSv3Ab7K9B4gZQohb77bVk3T0J9CNg8lNI1VRMWVFTKfkx6G59r
dTDgyFPlocoMMODCUvEQu0lzykQ1Yh5a47oEheEFVVN1XyPtaodY4jruKniWgkHs
oTZa3k7auhUozFeykQHlLhwuwFYCCaq/Nmyyi4C6HHfQxZc6Gsf2XijdmnRteu8e
uo5y1qtzDGOsGrjZKESICcrKLLrjLr82L6wlS2s2xg==
-----END CERTIFICATE-----
"""
run_installer()
