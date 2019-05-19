import libvirt
import xml.etree.ElementTree as ET

MB = 1024 * 1024
GB = MB * 1024


def connect(proto, user, address) -> libvirt.virConnect:
    connection_string = "{p}://{u}@{a}/system".format(
        p=proto, u=user, a=address)
    return libvirt.openReadOnly(connection_string)


def get_storage(conn: libvirt.virConnect, pool_cb, volume_cb):
    for pool in conn.listAllStoragePools():
        pool_dict = {"item": "pool"}
        pool_xml = pool.XMLDesc()
        pool_tree = ET.fromstring(pool_xml)
        pool_dict["type"] = pool_tree.attrib['type']
        pool_dict["name"] = pool_tree.find("name").text
        pool_dict["capacity"] = int(pool_tree.find("capacity").text) / GB
        pool_dict["available"] = int(pool_tree.find("available").text) / GB
        pool_cb(pool_dict)
        for volume in pool.listAllVolumes():
            volume_dict = {"item": "volume", "pool": pool_dict["name"]}
            volume_xml = volume.XMLDesc()
            # print(volume_xml)
            volume_tree = ET.fromstring(volume_xml)
            volume_dict["type"] = volume_tree.attrib['type']
            volume_dict["name"] = volume_tree.find('name').text
            volume_dict["capacity"] = int(volume_tree.find("capacity").text) / GB
            volume_cb(volume_dict)


if __name__ == "__main__":
    # conn = connect("qemu+ssh", "sdm", "farm1.prefis.sk")
    conn = connect("qemu", "", "")
    get_storage(conn, print, print)
