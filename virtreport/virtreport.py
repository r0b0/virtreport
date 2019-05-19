from typing import Callable

import libvirt
import xml.etree.ElementTree as ET

KB = 1024
MB = KB * 1024
GB = MB * 1024


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
            disk_dict = {"item": "disk", "host": hostname, "domain": dom_dict["name"]}
            disk_dict["type"] = disk_tree.attrib["type"]
            disk_dict["device"] = disk_tree.attrib["device"]
            source = disk_tree.find("source")
            if source is not None:
                disk_dict["source"] = source.attrib["dev"]
            else:
                disk_dict["source"] = ""
            disk_cb(disk_dict)


if __name__ == "__main__":
    conn = connect("qemu", "", "", print)
    get_storage(conn, print, print)
    get_domains(conn, print, print)
