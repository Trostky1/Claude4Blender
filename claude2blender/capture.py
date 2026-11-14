"""Capture identity for stale-result checks; no scene modifications."""
import hashlib
import json


def scene_signature():
    import bpy
    objects=[]
    for obj in bpy.context.scene.objects:
        entry=dict(name=obj.name, type=obj.type, matrix=[list(row) for row in obj.matrix_world],
                   hidden=obj.hide_render, materials=[s.material.name if s.material else None for s in obj.material_slots])
        if obj.type == "LIGHT":
            entry["light"]=[obj.data.energy, list(obj.data.color), obj.data.type]
        if obj.type == "CAMERA":
            entry["camera"]=[obj.data.lens, obj.data.dof.use_dof, obj.data.dof.focus_distance]
        if obj.type == "MESH":
            entry["mesh_counts"]=[len(obj.data.vertices),len(obj.data.polygons)]
        objects.append(entry)
    materials=[]
    for material in bpy.data.materials:
        if material.use_nodes:
            nodes=[]
            for node in material.node_tree.nodes:
                sockets=[]
                for socket in node.inputs:
                    value=getattr(socket,"default_value",None)
                    if value is not None:
                        sockets.append((socket.name,str(value) if isinstance(value,(str,int,float,bool)) else str(tuple(value)) if hasattr(value,"__iter__") else str(value)))
                nodes.append((node.name,node.bl_idname,sockets))
            materials.append((material.name,nodes,[(l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name) for l in material.node_tree.links]))
    data=dict(objects=objects,materials=materials, frame=bpy.context.scene.frame_current,
              camera=bpy.context.scene.camera.name if bpy.context.scene.camera else None,
              selected=sorted(o.name for o in bpy.context.selected_objects))
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
