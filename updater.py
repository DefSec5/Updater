#!/usr/bin/python3

import apt
import apt_pkg
from time import strftime
import os
import subprocess
import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import time

SYNAPTIC_PINFILE = "/var/lib/synaptic/preferences"
DISTRO = subprocess.check_output(["lsb_release", "-c", "-s"],
									universal_newlines=True).strip()
sender_email = "EMAIL HERE"
receiver_email = "EMAIL HERE"
log = 'updates.txt'

def email():
    message = MIMEMultipart()
    message["From"] = sender_email
    message['To'] = receiver_email
    message['Subject'] = "Update Check Completed!"
    attachment = open(log,'rb')
    obj = MIMEBase('application','octet-stream')
    obj.set_payload((attachment).read())
    encoders.encode_base64(obj)
    obj.add_header('Content-Disposition',"attachment; filename= "+log)
    message.attach(obj)
    my_message = message.as_string()
    email_session = smtplib.SMTP('smtp.gmail.com',587)
    email_session.starttls()
    email_session.login(sender_email,'GMAIL LOG IN TOKEN')
    email_session.sendmail(sender_email,receiver_email,my_message)
    email_session.quit()

def clean(cache, depcache):
	for pkg in cache.Packages:
		depcache.MarkKeep(pkg)
	depcache.init()

def saveDistUpgrade(cache,depcache):
	depcache.upgrade(True)
	if depcache.del_count > 0:
		clean(cache,depcache)
	depcache.upgrade()

def get_update_packages():
	pkgs = []
	apt_pkg.init()
	apt_pkg.config.set("Dir::Cache::pkgcache","")
	try:
		cache = apt_pkg.Cache(apt.progress.base.OpProgress())
	except SystemError as e:
		sys.stderr.write("Error: Opening the cache (%s)" % e)
		sys.exit(-1)
	depcache = apt_pkg.DepCache(cache)
	depcache.read_pinfile()
	if os.path.exists(SYNAPTIC_PINFILE):
		depcache.read_pinfile(SYNAPTIC_PINFILE)
	depcache.init()
	try:
		saveDistUpgrade(cache,depcache)
	except SystemError as e:
		sys.stderr.write("Error: Marking the upgrade (%s)" % e)
		sys.exit(-1)
	for pkg in cache.packages:
		if not (depcache.marked_install(pkg) or depcache.marked_upgrade(pkg)):
			continue
		inst_ver = pkg.current_ver
		cand_ver = depcache.get_candidate_ver(pkg)
		if cand_ver == inst_ver:
			continue
		record = {"name": pkg.name,
					"security": isSecurityUpgrade(pkg, depcache),
					"current_version": inst_ver.ver_str if inst_ver else '-',
					"candidate_version": cand_ver.ver_str if cand_ver else '-',
					"priority": cand_ver.priority_str}
		pkgs.append(record)
	return pkgs

def isSecurityUpgrade(pkg, depcache):
    def isSecurityUpgrade_helper(ver):
        security_pockets = [("Ubuntu", "%s-security" % DISTRO),
                            ("gNewSense", "%s-security" % DISTRO),
                            ("Debian", "%s-updates" % DISTRO)]
        for(file, index) in ver.file_list:
            for origin, archive in security_pockets:
                if (file.archive == archive and file.origin == origin):
                    return True
        return False
    inst_ver = pkg.current_ver
    cand_ver = depcache.get_candidate_ver(pkg)

    if isSecurityUpgrade_helper(cand_ver):
        return True
    for ver in pkg.version_list:
        if(inst_ver and apt_pkg.version_compare(ver.ver_str, inst_ver.ver_str) <= 0):
            continue
        if isSecurityUpgrade_helper(ver):
           return True
        return False

def logging():
    with open(log, 'w') as f:
            f.write(print_result(pkgs))

def print_result(pkgs):
    security_updates = filter(lambda x: x.get('security'), pkgs)
    text = list()
    text.append('Check Time: %s' % strftime('%m/%d/%Y %H:%M:%S'))
    if pkgs:
        text.append('Server: Pihole')
        text.append('The following packages can be updated:')
        text.append('-' * 65)
        text.append('Package Name'.ljust(20) +
                    'Current Version'.ljust(20) +
                    'Latest Version'.ljust(20) +
                    'Sec.'.ljust(5))
        text.append('-' * 65)
        for pkg in pkgs:
            text.append('{:<20}{:<20}{:<20}{:<5}'.format(pkg.get('name')[:16] + '..',
                pkg.get('current_version')[:16] + '..',
                pkg.get('candidate_version')[:16] + '..',
                '*' if pkg.get('security') else ''))
        text.append('=' * 65)
        return '\n'.join(text)
        logging()
        email()
    else:
        text.append('No available updates on this machine.')
        return

if __name__ == '__main__':
    pkgs = get_update_packages()
    print_result(pkgs)
