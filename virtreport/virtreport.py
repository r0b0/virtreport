import argparse
import sys
import traceback
from typing import Callable

import libvirt
import xml.etree.ElementTree as ET

import openpyxl

KB = 1024
MB = KB * 1024
GB = MB * 1024

# TODO hashbang
# TODO remove the first automatic sheet
# TODO sheet: host column mem_used =SUMIF(domain!A$2:A$62, host!A2, domain!E$2:E$62)
# TODO sheet: pool column host:pool =CONCATENATE(A2, ":", F2)
# TODO all sheets: column host by link
# TODO figure out how to calculate available space in pools and hosts
# TODO figure out how to handle migration of domains (and associated disks/volumes)


def connect(proto, user, address, host_cb: Callable) -> libvirt.virConnect:
    connection_string = "{p}://{u}@{a}/system".format(
        p=proto, u=user, a=address)
    conn = libvirt.openReadOnly(connection_string)
    host_dict = {"item": "host"}
    # https://libvirt.org/docs/libvirt-appdev-guide-python/en-US/html/ch03s04s03.html
    cpu, mem_mb, cpus, freq, numa, cpu_per_node, core_per_cpu, thread_per_core = conn.getInfo()
    host_dict["host"] = conn.getHostname()
    host_dict["cpu_type"] = cpu
    host_dict["mem"] = mem_mb / KB
    host_dict["freq"] = freq
    host_dict["cores"] = numa * cpu_per_node * core_per_cpu * thread_per_core
    host_cb(host_dict)
    return conn


def get_storage(conn: libvirt.virConnect, pool_cb: Callable, volume_cb: Callable) -> None:
    hostname = conn.getHostname()
    for pool in conn.listAllStoragePools():
        if not pool.isActive():
            print("Pool {p} is not active, skipping".format(p=pool.name()))
            continue
        pool_dict = {"item": "pool", "host": hostname}
        pool_xml = pool.XMLDesc()
        pool_tree = ET.fromstring(pool_xml)
        pool_dict["type"] = pool_tree.attrib['type']
        pool_dict["name"] = pool_tree.find("name").text
        pool_dict["capacity"] = int(pool_tree.find("capacity").text) / GB
        pool_dict["available"] = int(pool_tree.find("available").text) / GB
        pool_cb(pool_dict)
        for volume in pool.listAllVolumes():
            volume_dict = {"item": "volume", "host": hostname, "pool": pool_dict["name"]}
            volume_xml = volume.XMLDesc()
            # print(volume_xml)
            volume_tree = ET.fromstring(volume_xml)
            volume_dict["type"] = volume_tree.attrib['type']
            volume_dict["name"] = volume_tree.find('name').text
            volume_dict["target"] = volume_tree.find("target/path").text
            # capacity is reported in bytes
            volume_dict["capacity"] = int(volume_tree.find("capacity").text) / GB
            volume_cb(volume_dict)


def get_domains(conn: libvirt.virConnect, dom_cb: Callable, disk_cb: Callable) -> None:
    hostname = conn.getHostname()
    for domain in conn.listAllDomains():
        dom_dict = {"item": "domain", "host": hostname}
        dom_xml = domain.XMLDesc()
        # print(dom_xml)
        dom_tree = ET.fromstring(dom_xml)
        dom_dict["name"] = dom_tree.find("name").text
        desc = dom_tree.find("description")
        if desc is not None:
            dom_dict["description"] = desc.text
        else:
            dom_dict["description"] = ""
        # memory is reported in kBytes
        dom_dict["memory"] = int(dom_tree.find("memory").text) / MB
        dom_dict["currentMemory"] = int(dom_tree.find("currentMemory").text) / MB
        dom_dict["vcpu"] = int(dom_tree.find("vcpu").text)
        dom_dict["active"] = domain.isActive()
        dom_cb(dom_dict)
        for disk_tree in dom_tree.findall("devices/disk"):
            # print(ET.tostring(disk_tree))
            disk_dict = {"item": "disk", "host": hostname, "domain": dom_dict["name"]}
            disk_dict["type"] = disk_tree.attrib["type"]
            disk_dict["device"] = disk_tree.attrib["device"]
            source = disk_tree.find("source")
            if source is not None:
                if "dev" in source.attrib:
                    disk_dict["source"] = source.attrib["dev"]
                elif "file" in source.attrib:
                    disk_dict["source"] = source.attrib["file"]
            else:
                disk_dict["source"] = ""
            disk_cb(disk_dict)


def save_item(worksheet: openpyxl.Workbook, item: dict):
    for sheet in worksheet:
        # existing sheet, we just append
        if sheet.title == item["item"]:
            sheet.append(list(item.values()))
            return
    # no existing sheet, create one
    sheet = worksheet.create_sheet(item["item"])
    sheet.append(list(item.keys()))  # header row
    sheet.append(list(item.values()))


def parse_arguments():
    parser = argparse.ArgumentParser("virtreport")
    parser.add_argument("-p", "--protocol", default="qemu")
    parser.add_argument("-u", "--user", default="")
    parser.add_argument("-o", "--output", default="virt_report.xlsx")
    parser.add_argument("hosts", nargs="*", default=[""])
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    wb = openpyxl.Workbook()
    save_item_lambda = lambda i: save_item(wb, i)
    for host in args.hosts:
        print("Connecting to {h}".format(h=host))
        try:
            conn = connect(args.protocol, args.user, host, save_item_lambda)
            get_storage(conn, save_item_lambda, save_item_lambda)
            get_domains(conn, save_item_lambda, save_item_lambda)
        except:
            print("Failed to connect to {h}".format(h=host), file=sys.stderr)
            traceback.print_exc()
    print("Saving report to {r}".format(r=args.output))
    wb.save(args.output)

