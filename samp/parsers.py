import math
from typing import Callable

from core.bitstream import BitStream
from core import logger
from .interfaces import parse_json_payload
from .constants import (
    PacketID,
    RPC as RPCConstants
)



class RPCParser:

    @staticmethod
    def server_quit(bs: BitStream) -> dict | None:

        player_id = bs.read_uint16()
        reason = bs.read_uint8()

        return {
            "player_id": player_id,
            "reason": reason
        }

    @staticmethod
    def server_join(bs: BitStream) -> dict | None:

        player_id = bs.read_uint16()
        color = bs.read_uint32()
        is_npc = bs.read_uint8()
        bs.skip_bits(64)
        name = bs.read_string(
            bs.read_uint8(),
            "cp1251",
            errors="ignore"
        )

        return {
            "player_id": player_id,
            "color": color,
            "is_npc": is_npc,
            "name": name
        }


    @staticmethod
    def init_game(bs: BitStream) -> dict | None:
        
        bs.skip_bits(72)
        d_spawns_available = bs.read_uint32()

        player_id = bs.read_uint16()

        bs.skip_bits(3)
        bs.skip_bits(272)

        hostname = bs.read_string(
            bs.read_uint8(),
            "cp1251",
            errors="ignore"
        )

        return {
            "player_id": player_id,
            "hostname": hostname,
            "d_spawns_available": d_spawns_available
        }


    @staticmethod
    def connection_rejected(bs: BitStream) -> dict | None:
        reason_kick = bs.read_uint8()

        return {
            "reason_kick": reason_kick
        }


    @staticmethod
    def set_spawn_info(bs: BitStream) -> dict | None:

        team = bs.read_uint8()
        skin = bs.read_uint32()

        unused = bs.read_uint8()

        x = bs.read_float()
        y = bs.read_float()
        z = bs.read_float()

        rotation = bs.read_float()

        weapon1 = bs.read_uint32()
        weapon2 = bs.read_uint32()
        weapon3 = bs.read_uint32()

        ammo1 = bs.read_uint32()
        ammo2 = bs.read_uint32()
        ammo3 = bs.read_uint32()

        return {
            "team": team,
            "skin": skin,


            "x": x,
            "y": y,
            "z": z,

            "rotation": rotation,

            "weapon1": weapon1,
            "weapon2": weapon2,
            "weapon3": weapon3,

            "ammo1": ammo1,
            "ammo2": ammo2,
            "ammo3": ammo3,
        }


    @staticmethod
    def request_spawn(bs: BitStream) -> dict | None:
        spawn_response = bs.read_uint8()

        return {
            "spawn_response": spawn_response
        }


    @staticmethod
    def client_message(bs: BitStream) -> dict | None:

        bs.skip_bits(32)

        message = bs.read_string(
            bs.read_uint32(),
            "utf-8",
            errors="ignore"
        )

        return {
            "message": message
        }


    @staticmethod
    def update_scores_and_pings(bs: BitStream) -> dict | None:
        entries = []

        while bs.remaining_bits >= 80:
            player_id = bs.read_uint16()
            score = bs.read_int32()
            ping = bs.read_uint32()

            entries.append({
                "player_id": int(player_id),
                "score": int(score),
                "ping": int(ping),
            })

        return {
            "scores_and_pings": entries,
        }


    @staticmethod
    def show_dialog(bs: BitStream) -> dict | None:
        dialog_id = bs.read_uint16()
        style = bs.read_uint8()

        title = bs.read_string(
            bs.read_uint8(),
            "utf-8",
            errors="ignore"
        )
        button1 = bs.read_string(
            bs.read_uint8(),
            "utf-8",
            errors="ignore"
        )
        button2 = bs.read_string(
            bs.read_uint8(),
            "utf-8",
            errors="ignore"
        )

        info_len = bs.read_uint32()

        info = bs.read_string(
            info_len,
            "utf-8",
            errors="ignore"
        )

        return {
            "dialog_id": dialog_id,
            "dialog_style": style,
            "dialog_title": title,
            "dialog_button1": button1,
            "dialog_button2": button2,
            "dialog_info_len": info_len,
            "dialog_info": info,
        }


    @staticmethod
    def set_player_name(bs: BitStream) -> dict | None:
        player_id = bs.read_uint16()
        name = bs.read_string(
            bs.read_uint8(),
            "cp1251",
            errors="ignore"
        )

        success = bs.read_bool()

        return {
            "player_id": player_id,
            "name": name,
            "success": success
        }


    @staticmethod
    def set_player_pos(bs: BitStream) -> dict | None:

        x = bs.read_float()
        y = bs.read_float()
        z = bs.read_float()
        
        return {
            "x": x,
            "y": y,
            "z": z
        }


    @staticmethod
    def set_player_facing_angle(bs: BitStream) -> dict | None:

        rotation = bs.read_float()

        return {
            "rotation": rotation
        }

    @staticmethod
    def set_player_skin(bs: BitStream) -> dict | None:

        player_id = bs.read_uint32()
        skin_id = bs.read_uint32()

        return {
            "player_id": player_id,
            "skin": skin_id
        }

    @staticmethod
    def give_player_money(bs: BitStream) -> dict | None:
        amount = bs.read_int32()

        return {
            "amount": int(amount),
        }


    @staticmethod
    def play_audio_stream(bs: BitStream) -> dict | None:
        bs.skip_bits(32)
        url = bs.read_string(
            bs.read_uint8(),
            "ascii",
            errors="ignore"
        )


        return {
            "url": url,
        }

    @staticmethod
    def stop_audio_stream(bs: BitStream) -> dict | None:
        return {}


    @staticmethod
    def set_player_health(bs: BitStream) -> dict | None:

        health = bs.read_float()

        return {
            "health": float(health)
        }


    @staticmethod
    def set_player_armour(bs: BitStream) -> dict | None:

        armour = bs.read_float()

        return {
            "armour": armour
        }

    @staticmethod
    def set_weapon_ammo(bs: BitStream) -> dict | None:
        weapon_id = bs.read_uint8()
        ammo = bs.read_uint16()

        return {
            "weapon_id": weapon_id,
            "ammo": ammo
        }


    @staticmethod
    def set_camera_behind(bs: BitStream) -> dict:
        return {}

    @staticmethod
    def world_player_add(bs: BitStream) -> dict | None:
        player_id = bs.read_uint16()
        skin_id = bs.read_uint32()
        pos_x = bs.read_float()
        pos_y = bs.read_float()
        pos_z = bs.read_float()
        facing_angle = bs.read_float()
        fighting_style = bs.read_uint8()
        health = bs.read_float()
        armour = bs.read_float()
        raw_extra = b''
        if bs.remaining_bits >= 8:
            raw_extra = bs.read_bytes(bs.remaining_bits // 8)
        return {'player_id': int(player_id), 'skin_id': int(skin_id), 'x': float(pos_x), 'y': float(pos_y), 'z': float(pos_z), 'facing_angle': float(facing_angle), 'fighting_style': int(fighting_style), 'health': health, 'armour': armour, 'raw_extra': raw_extra.hex()}


    @staticmethod
    def world_player_remove(bs: BitStream) -> dict | None:

        player_id = bs.read_uint16()

        return {
            "player_id": int(player_id),
        }

    @staticmethod
    def world_player_death(bs: BitStream) -> dict | None:

        player_id = bs.read_uint16()

        return {
            "player_id": int(player_id),
        }

    @staticmethod
    def apply_player_animation(bs: BitStream) -> dict | None:

        player_id = bs.read_uint16()

        anim_lib = bs.read_string(
            bs.read_uint8(),
            "cp1251",
            errors="ignore"
        )

        anim_name = bs.read_string(
            bs.read_uint8(),
            "cp1251",
            errors="ignore"
        )

        delta = bs.read_float()

        loop = bs.read_bool()
        lock_x = bs.read_bool()
        lock_y = bs.read_bool()
        freeze = bs.read_bool()

        duration_ms = bs.read_uint32()

        return {
            "player_id": int(player_id),
            "anim_lib": anim_lib,
            "anim_name": anim_name,
            "delta": float(delta),
            "loop": bool(loop),
            "lock_x": bool(lock_x),
            "lock_y": bool(lock_y),
            "freeze": bool(freeze),
            "duration_ms": int(duration_ms),
        }

    @staticmethod
    def clear_player_animation(bs: BitStream) -> dict | None:

        player_id = bs.read_uint16()

        return {
            "player_id": int(player_id),
        }


    @staticmethod
    def world_vehicle_add(bs: BitStream) -> dict | None:
        vehicle_id = bs.read_uint16()
        model_id = bs.read_uint32()
        x = bs.read_float()
        y = bs.read_float()
        z = bs.read_float()
        rotation = bs.read_float()
        color1 = bs.read_uint8()
        color2 = bs.read_uint8()
        health = bs.read_float()
        interior = bs.read_uint8()
        raw_extra = b''
        if bs.remaining_bits >= 8:
            raw_extra = bs.read_bytes(bs.remaining_bits // 8)
        return {'vehicle_id': vehicle_id, 'model_id': model_id, 'x': x, 'y': y, 'z': z, 'rotation': rotation, 'color1': color1, 'color2': color2, 'health': float(health), 'interior': interior, 'raw_extra': raw_extra.hex()}


    @staticmethod
    def world_vehicle_remove(bs: BitStream) -> dict | None:

        vehicle_id = bs.read_uint16()

        return {
            "vehicle_id": int(vehicle_id),
        }


    @staticmethod
    def create_pickup(bs: BitStream) -> dict | None:
        pickup_id = bs.read_int32()
        model_id = bs.read_int32()
        spawn_type = bs.read_int32()

        x = bs.read_float()
        y = bs.read_float()
        z = bs.read_float()

        return {
            "pickup_id": int(pickup_id),
            "model_id": int(model_id),
            "spawn_type": int(spawn_type),
            "x": float(x),
            "y": float(y),
            "z": float(z),
        }


    @staticmethod
    def destroy_pickup(bs: BitStream) -> dict | None:

        pickup_id = bs.read_int32()

        return {
            "pickup_id": int(pickup_id),
        }


    @staticmethod
    def set_map_icon(bs: BitStream) -> dict | None:
        icon_id = bs.read_uint16()
        x = bs.read_float()
        y = bs.read_float()
        z = bs.read_float()
        marker_type = bs.read_uint8()
        color = bs.read_uint32()
        style = bs.read_uint8()
        raw_extra = b''
        if bs.remaining_bits >= 8:
            raw_extra = bs.read_bytes(bs.remaining_bits // 8)
        return {'icon_id': icon_id, 'x': x, 'y': y, 'z': z, 'marker_type': marker_type, 'color': color, 'style': style, 'raw_extra': raw_extra.hex()}


    @staticmethod
    def create_3d_text_label(bs: BitStream) -> dict | None:
        label_id = bs.read_uint16()
        color = bs.read_uint32()
        x = bs.read_float()
        y = bs.read_float()
        z = bs.read_float()
        draw_distance = bs.read_float()
        use_los_raw = bs.read_uint8()
        attached_player_id = bs.read_uint16()
        attached_vehicle_id = bs.read_uint16()
        text = bs.read_cstring('cp1251', errors='ignore', max_length=4096)
        return {'label_id': int(label_id), 'color': int(color), 'x': float(x), 'y': float(y), 'z': float(z), 'draw_distance': float(draw_distance), 'use_los': bool(use_los_raw), 'attached_player_id': int(attached_player_id), 'attached_vehicle_id': int(attached_vehicle_id), 'text': text}


    @staticmethod
    def delete_3d_text_label(bs: BitStream) -> dict | None:

        label_id = bs.read_uint16()

        return {
            "label_id": int(label_id),
        }

    @staticmethod
    def remove_map_icon(bs: BitStream) -> dict | None:

        icon_id = bs.read_uint8()

        return {
            "icon_id": int(icon_id),
        }


    @staticmethod
    def set_interior(bs: BitStream) -> dict | None:

        interior_id = bs.read_uint8()

        return {
            "interior_id": interior_id
        }


    @staticmethod
    def set_camera_pos(bs: BitStream) -> dict | None:

        x = bs.read_float()
        y = bs.read_float()
        z = bs.read_float()
        
        return {
            "xCam": x,
            "yCam": y,
            "zCam": z
        }

    @staticmethod
    def enter_vehicle(bs: BitStream) -> dict | None:
        player_id = bs.read_uint16()
        vehicle_id = bs.read_uint16()
        is_passenger = bs.read_uint8()
        raw_extra = b''
        if bs.remaining_bits >= 8:
            raw_extra = bs.read_bytes(bs.remaining_bits // 8)
        return {'player_id': int(player_id), 'vehicle_id': int(vehicle_id), 'is_passenger': int(is_passenger), 'raw_extra': raw_extra.hex()}


    @staticmethod
    def put_player_in_vehicle(bs: BitStream) -> dict | None:
        vehicle_id = bs.read_uint16()
        seat_id = bs.read_uint8()
        raw_extra = b''
        if bs.remaining_bits >= 8:
            raw_extra = bs.read_bytes(bs.remaining_bits // 8)
        return {'vehicle_id': int(vehicle_id), 'seat_id': int(seat_id), 'raw_extra': raw_extra.hex()}

    @staticmethod
    def remove_player_from_vehicle(bs: BitStream) -> dict | None:
        return {}


    @staticmethod
    def set_vehicle_z_angle(bs: BitStream) -> dict | None:

        vehicle_id = bs.read_uint16()
        rotation = bs.read_float()

        return {
            "vehicle_id": int(vehicle_id),
            "rotation": float(rotation),
        }


    @staticmethod
    def give_player_weapon(bs: BitStream) -> dict | None:

        weapon_id = bs.read_uint8()
        ammo = bs.read_uint32()

        return {
            "weapon_id": int(weapon_id),
            "ammo": int(ammo),
        }

    @staticmethod
    def reset_player_weapons(bs: BitStream) -> dict | None:
        return {}


    @staticmethod
    def set_vehicle_pos(bs: BitStream) -> dict | None:
        vehicle_id = bs.read_uint16()
        x = bs.read_float()
        y = bs.read_float()
        z = bs.read_float()
        raw_extra = b''
        if bs.remaining_bits >= 8:
            raw_extra = bs.read_bytes(bs.remaining_bits // 8)
        return {'vehicle_id': int(vehicle_id), 'x': float(x), 'y': float(y), 'z': float(z), 'raw_extra': raw_extra.hex()}


    @staticmethod
    def set_player_velocity(bs: BitStream) -> dict | None:
        velocity_x = bs.read_float()
        velocity_y = bs.read_float()
        velocity_z = bs.read_float()
        raw_extra = b''
        if bs.remaining_bits >= 8:
            raw_extra = bs.read_bytes(bs.remaining_bits // 8)
        return {'velocity_x': float(velocity_x), 'velocity_y': float(velocity_y), 'velocity_z': float(velocity_z), 'velocity': (float(velocity_x), float(velocity_y), float(velocity_z)), 'raw_extra': raw_extra.hex()}


    @staticmethod
    def set_vehicle_velocity(bs: BitStream) -> dict | None:
        turn = bs.read_uint8()
        velocity_x = bs.read_float()
        velocity_y = bs.read_float()
        velocity_z = bs.read_float()
        raw_extra = b''
        if bs.remaining_bits >= 8:
            raw_extra = bs.read_bytes(bs.remaining_bits // 8)
        return {'turn': int(turn), 'velocity_x_car': float(velocity_x), 'velocity_y_car': float(velocity_y), 'velocity_z_car': float(velocity_z), 'velocity': (float(velocity_x), float(velocity_y), float(velocity_z)), 'raw_extra': raw_extra.hex()}


    @staticmethod
    def reset_player_money(bs: BitStream) -> dict | None:
        return {}

    @staticmethod
    def show_game_text(bs: BitStream) -> dict | None:

        style = bs.read_uint32()
        time = bs.read_uint32()
        message_length = bs.read_uint32()

        text = (
            bs.read_string(message_length, "cp1251", errors="ignore")
            if message_length > 0
            else ""
        )

        return {
            "style": int(style),
            "time": int(time),
            "text": text,
        }

    @staticmethod
    def set_checkpoint(bs: BitStream) -> dict | None:

        x = bs.read_float()
        y = bs.read_float()
        z = bs.read_float()
        radius = bs.read_float()

        return {
            "xCP": float(x),
            "yCP": float(y),
            "zCP": float(z),
            "fRadius": float(radius),
        }

    @staticmethod
    def disable_checkpoint(bs: BitStream) -> dict | None:
        return {}

    @staticmethod
    def game_mode_restart(bs: BitStream) -> dict | None:
        return {}

    @staticmethod
    def set_race_checkpoint(bs: BitStream) -> dict | None:

        cp_type = bs.read_uint8()

        x = bs.read_float()
        y = bs.read_float()
        z = bs.read_float()

        next_x = bs.read_float()
        next_y = bs.read_float()
        next_z = bs.read_float()

        radius = bs.read_float()

        return {
            "type": int(cp_type),
            "xCP": float(x),
            "yCP": float(y),
            "zCP": float(z),
            "xNextCP": float(next_x),
            "yNextCP": float(next_y),
            "zNextCP": float(next_z),
            "fRadius": float(radius),
        }

    @staticmethod
    def disable_race_checkpoint(bs: BitStream) -> dict | None:
        return {}

    @staticmethod
    def toggle_player_controllable(bs: BitStream) -> dict | None:

        moveable = bs.read_uint8()

        return {
            "frozen": not bool(moveable),
        }

    @staticmethod
    def show_text_draw(bs: BitStream) -> dict | None:
        wTextDrawID = bs.read_uint16()
        flags = bs.read_uint8()
        fLetterWidth = bs.read_float()
        fLetterHeight = bs.read_float()
        dLetterColor = bs.read_uint32()
        fLineWidth = bs.read_float()
        fLineHeight = bs.read_float()
        dBoxColor = bs.read_uint32()
        shadow = bs.read_uint8()
        outline = bs.read_uint8()
        dBackgroundColor = bs.read_uint32()
        style = bs.read_uint8()
        selectable = bs.read_uint8()
        fX = bs.read_float()
        fY = bs.read_float()
        wModelID = bs.read_uint16()
        fRotX = bs.read_float()
        fRotY = bs.read_float()
        fRotZ = bs.read_float()
        fZoom = bs.read_float()
        wColor1 = bs.read_uint16()
        wColor2 = bs.read_uint16()
        szTextLen = bs.read_uint16()
        szText = bs.read_string(szTextLen, "cp1251", errors="ignore") if szTextLen > 0 else ""

        return {
            "textdraw_id": wTextDrawID,
            "flags": flags,
            "letter_width": fLetterWidth,
            "letter_height": fLetterHeight,
            "letter_color": dLetterColor,
            "line_width": fLineWidth,
            "line_height": fLineHeight,
            "box_color": dBoxColor,
            "shadow": shadow,
            "outline": outline,
            "background_color": dBackgroundColor,
            "style": style,
            "selectable": selectable,
            "x": fX,
            "y": fY,
            "model_id": wModelID,
            "rot_x": fRotX,
            "rot_y": fRotY,
            "rot_z": fRotZ,
            "zoom": fZoom,
            "color1": wColor1,
            "color2": wColor2,
            "text": szText,
        }

    @staticmethod
    def text_draw_set_string(bs: BitStream) -> dict | None:
        wTextDrawID = bs.read_uint16()
        textLength = bs.read_uint16()
        text = bs.read_string(textLength, "cp1251", errors="ignore") if textLength > 0 else ""

        return {
            "textdraw_id": wTextDrawID,
            "text": text,
        }

    @staticmethod
    def hide_text_draw(bs: BitStream) -> dict | None:
        wTextDrawID = bs.read_uint16()

        return {
            "textdraw_id": wTextDrawID,
        }

    @staticmethod
    def set_vehicle_params(bs: BitStream) -> dict | None:
        vehicle_id = bs.read_uint16()
        params = []
        params_format = 'int32'
        while bs.remaining_bits >= 32:
            params.append(int(bs.read_int32()))
        raw_extra = b''
        if bs.remaining_bits >= 8:
            raw_extra = bs.read_bytes(bs.remaining_bits // 8)
        result = {'state': 'set_vehicle_params', 'vehicle_id': int(vehicle_id), 'params': params, 'params_format': params_format, 'raw_extra': raw_extra.hex()}
        names = ('engine', 'lights', 'alarm', 'doors', 'bonnet', 'boot', 'objective', 'siren')
        for index, name in enumerate(names):
            if index < len(params):
                result[name] = params[index]
        return result



RPC_PARSE_REGISTRY: dict[str, tuple[int, "Callable[[BitStream], dict | None]"]] = {
    "request_spawn": (
        RPCConstants.REQUEST_SPAWN,
        RPCParser.request_spawn,
    ),
    "update_scores_and_pings": (
        RPCConstants.UPDATE_SCORES_PINGS_IPS,
        RPCParser.update_scores_and_pings,
    ),
    "give_player_money": (
        RPCConstants.SCR_GIVE_PLAYER_MONEY,
        RPCParser.give_player_money,
    ),
    "show_dialog": (
        RPCConstants.SCR_DIALOG_BOX,
        RPCParser.show_dialog,
    ),
    "client_message": (
        RPCConstants.CLIENT_MESSAGE,
        RPCParser.client_message,
    ),
    "server_quit": (
        RPCConstants.SERVER_QUIT,
        RPCParser.server_quit,
    ),
    "connection_rejected": (
        RPCConstants.CONNECTION_REJECTED,
        RPCParser.connection_rejected,
    ),
    "server_join": (
        RPCConstants.SERVER_JOIN,
        RPCParser.server_join,
    ),
    "init_game": (
        RPCConstants.INIT_GAME,
        RPCParser.init_game,
    ),
    "set_spawn_info": (
        RPCConstants.SCR_SET_SPAWN_INFO,
        RPCParser.set_spawn_info,
    ),
    "set_player_name": (
        RPCConstants.SCR_SET_PLAYER_NAME,
        RPCParser.set_player_name,
    ),
    "set_player_pos": (
        RPCConstants.SCR_SET_PLAYER_POS,
        RPCParser.set_player_pos,
    ),
    "set_player_pos_find_z": (
        RPCConstants.SCR_SET_PLAYER_POS_FIND_Z,
        RPCParser.set_player_pos,
    ),
    "set_player_facing_angle": (
        RPCConstants.SCR_SET_PLAYER_FACING_ANGLE,
        RPCParser.set_player_facing_angle,
    ),
    "set_player_skin": (
        RPCConstants.SCR_SET_PLAYER_SKIN,
        RPCParser.set_player_skin,
    ),
    "play_audio_stream": (
        RPCConstants.PLAY_AUDIO_STREAM,
        RPCParser.play_audio_stream,
    ),
    "stop_audio_stream": (
        RPCConstants.STOP_AUDIO_STREAM,
        RPCParser.stop_audio_stream,
    ),
    "set_player_health": (
        RPCConstants.SCR_SET_PLAYER_HEALTH,
        RPCParser.set_player_health,
    ),
    "set_player_armour": (
        RPCConstants.SCR_SET_PLAYER_ARMOUR,
        RPCParser.set_player_armour,
    ),
    "set_weapon_ammo": (
        RPCConstants.SCR_SET_WEAPON_AMMO,
        RPCParser.set_weapon_ammo,
    ),
    "give_player_weapon": (
        RPCConstants.SCR_GIVE_PLAYER_WEAPON,
        RPCParser.give_player_weapon,
    ),
    "reset_player_weapons": (
        RPCConstants.SCR_RESET_PLAYER_WEAPONS,
        RPCParser.reset_player_weapons,
    ),
    "set_camera_behind": (
        RPCConstants.SCR_SET_CAMERA_BEHIND_PLAYER,
        RPCParser.set_camera_behind,
    ),
    "world_player_add": (
        RPCConstants.WORLD_PLAYER_ADD,
        RPCParser.world_player_add,
    ),
    "world_player_remove": (
        RPCConstants.WORLD_PLAYER_REMOVE,
        RPCParser.world_player_remove,
    ),
    "world_player_death": (
        RPCConstants.WORLD_PLAYER_DEATH,
        RPCParser.world_player_death,
    ),
    "apply_player_animation": (
        RPCConstants.SCR_APPLY_ANIMATION,
        RPCParser.apply_player_animation,
    ),
    "clear_player_animation": (
        RPCConstants.SCR_CLEAR_ANIMATIONS,
        RPCParser.clear_player_animation,
    ),
    "world_vehicle_add": (
        RPCConstants.WORLD_VEHICLE_ADD,
        RPCParser.world_vehicle_add,
    ),
    "world_vehicle_remove": (
        RPCConstants.WORLD_VEHICLE_REMOVE,
        RPCParser.world_vehicle_remove,
    ),
    "set_map_icon": (
        RPCConstants.SCR_SET_MAP_ICON,
        RPCParser.set_map_icon,
    ),
    "remove_map_icon": (
        RPCConstants.SCR_DISABLE_MAP_ICON,
        RPCParser.remove_map_icon,
    ),
    "create_pickup": (
        RPCConstants.CREATE_PICKUP,
        RPCParser.create_pickup,
    ),
    "destroy_pickup": (
        RPCConstants.DESTROY_PICKUP,
        RPCParser.destroy_pickup,
    ),
    "create_3d_text_label": (
        RPCConstants.SCR_CREATE_3D_TEXT_LABEL,
        RPCParser.create_3d_text_label,
    ),
    "delete_3d_text_label": (
        RPCConstants.SCR_DELETE_3D_TEXT_LABEL,
        RPCParser.delete_3d_text_label,
    ),
    "set_interior": (
        RPCConstants.SCR_SET_INTERIOR,
        RPCParser.set_interior,
    ),
    "set_camera_pos": (
        RPCConstants.SCR_SET_CAMERA_POS,
        RPCParser.set_camera_pos,
    ),
    "enter_vehicle": (
        RPCConstants.ENTER_VEHICLE,
        RPCParser.enter_vehicle,
    ),
    "put_player_in_vehicle": (
        RPCConstants.SCR_PUT_PLAYER_IN_VEHICLE,
        RPCParser.put_player_in_vehicle,
    ),
    "remove_player_from_vehicle": (
        RPCConstants.SCR_REMOVE_PLAYER_FROM_VEHICLE,
        RPCParser.remove_player_from_vehicle,
    ),
    "set_vehicle_z_angle": (
        RPCConstants.SCR_SET_VEHICLE_Z_ANGLE,
        RPCParser.set_vehicle_z_angle,
    ),
    "set_vehicle_pos": (
        RPCConstants.SCR_SET_VEHICLE_POS,
        RPCParser.set_vehicle_pos,
    ),
    "set_player_velocity": (
        RPCConstants.SCR_SET_PLAYER_VELOCITY,
        RPCParser.set_player_velocity,
    ),
    "set_vehicle_velocity": (
        RPCConstants.SCR_SET_VEHICLE_VELOCITY,
        RPCParser.set_vehicle_velocity,
    ),
    "set_vehicle_params": (
        RPCConstants.SCR_VEHICLE_PARAMS,
        RPCParser.set_vehicle_params,
    ),
    "reset_player_money": (
        RPCConstants.SCR_RESET_MONEY,
        RPCParser.reset_player_money,
    ),
    "show_game_text": (
        RPCConstants.SCR_DISPLAY_GAME_TEXT,
        RPCParser.show_game_text,
    ),
    "set_checkpoint": (
        RPCConstants.SET_CHECKPOINT,
        RPCParser.set_checkpoint,
    ),
    "disable_checkpoint": (
        RPCConstants.DISABLE_CHECKPOINT,
        RPCParser.disable_checkpoint,
    ),
    "game_mode_restart": (
        RPCConstants.GAME_MODE_RESTART,
        RPCParser.game_mode_restart,
    ),
    "set_race_checkpoint": (
        RPCConstants.SET_RACE_CHECKPOINT,
        RPCParser.set_race_checkpoint,
    ),
    "disable_race_checkpoint": (
        RPCConstants.DISABLE_RACE_CHECKPOINT,
        RPCParser.disable_race_checkpoint,
    ),
    "toggle_player_controllable": (
        RPCConstants.SCR_TOGGLE_PLAYER_CONTROLLABLE,
        RPCParser.toggle_player_controllable,
    ),
    "show_text_draw": (
        RPCConstants.SCR_SHOW_TEXT_DRAW,
        RPCParser.show_text_draw,
    ),
    "text_draw_set_string": (
        RPCConstants.SCR_TEXT_DRAW_SET_STRING,
        RPCParser.text_draw_set_string,
    ),
    "hide_text_draw": (
        RPCConstants.SCR_HIDE_TEXT_DRAW,
        RPCParser.hide_text_draw,
    ),
}

RPC_PARSERS = {
    rpc_id: (name, parser)
    for name, (rpc_id, parser) in RPC_PARSE_REGISTRY.items()
}



RPC_PARSERS[362] = ("give_player_money", RPCParser.give_player_money)
RPC_PARSERS[319] = ("connection_rejected", RPCParser.connection_rejected)
RPC_PARSERS[421] = ("init_game", RPCParser.init_game)
RPC_PARSERS[309] = ("delete_3d_text_label", RPCParser.delete_3d_text_label)


class RPC:

    @staticmethod
    def _read_rpc_id(
        bs: BitStream
    ) -> int:

        rpc_id = bs.read_uint8() | (bs.read_bits(1) << 8)
        bs.read_bits(2)
        return rpc_id

    @staticmethod
    def _bits_to_bytes(value: int, bitlen: int) -> bytes:
        if bitlen <= 0:
            return b""

        count = (bitlen + 7) // 8
        pad = count * 8 - bitlen

        if pad:
            value <<= pad

        return value.to_bytes(count, "big")

    @staticmethod
    def _parse_payload(
        rpc_id: int,
        payload: bytes
    ) -> tuple[dict | None, BitStream | None]:
        entry = RPC_PARSERS.get(rpc_id)

        if entry is None:
            return None, None

        rpc_name, rpc_parser = entry

        payload_bs = BitStream(payload)

        try:
            parsed = rpc_parser(payload_bs)
        except Exception as error:
            logger.rpc_parse_error(
                f"RPC PAYLOAD PARSE ERROR"
                f"id={rpc_id} parser={rpc_parser.__name__}: {error}"
            )
            return None, payload_bs

        if parsed is not None:
            parsed.setdefault("state", rpc_name)

        return parsed, payload_bs

    @staticmethod
    def read_rpc(data: bytes) -> dict | None:

        if len(data) < 2:
            return None

        try:

            bs = BitStream(data)

            rpc_id = RPC._read_rpc_id(bs)

            bitlen = bs.read_compressed(16, unsigned=True)

            if bitlen > bs.remaining_bits:
                logger.rpc_parse_error(
                    f"RPC ERROR Not enough bits: "
                    f"need {bitlen}, have {bs.remaining_bits} "
                    f"rpc_id={rpc_id} "
                    f"body_len={len(data)} "
                    f"first_4_bytes={data[:4].hex()}"
                )
                return None

            payload_value = bs.read_bits(bitlen)
            payload_bytes = RPC._bits_to_bytes(payload_value, bitlen)

            parsed_payload, payload_bs = RPC._parse_payload(
                rpc_id,
                payload_bytes
            )

            return {
                "rpc_id": rpc_id,
                "payload": payload_bytes,
                "parsed_payload": parsed_payload,
                "raw": data,
            }

        except Exception as e:

            logger.rpc_parse_error(f"{e}")

            return None

class PacketParser:

    @staticmethod
    def open_connection_reply(
        data: bytes
    ) -> dict:

        return {
            "raw": data
        }

    @staticmethod
    def open_connection_cookie(
        data: bytes
    ) -> dict | None:

        if len(data) < 2:
            return None

        cookie = (data[0] << 8) | data[1]

        return {
            "cookie": cookie,
            "raw": data
        }

    @staticmethod
    def auth_key(
        data: bytes
    ) -> dict | None:

        if len(data) < 2:
            return None

        key_len = data[0]

        
        
        
        
        
        
        
        if key_len not in (0x60, 24):
            return None

        if len(data) < 1 + key_len:
            return None

        key = data[1:1 + key_len].decode(
            "ascii",
            errors="ignore"
        )

        terminator = (
            data[1 + key_len]
            if len(data) > 1 + key_len
            else None
        )

        return {
            "type": "auth_key",
            "key": key,
            "key_len": key_len,
            "terminator": terminator,
            "raw": data
        }

    @staticmethod
    def connection_request_accepted(
        data: bytes
    ) -> dict:

        return {
            "type": "connection_request_accepted",
            "raw": data
        }

    @staticmethod
    def internal_ping(
        data: bytes
    ) -> dict | None:

        if len(data) < 4:
            return None

        bs = BitStream(data)
        sender_ms = bs.read_uint32()

        return {
            "sender_ms": sender_ms,
            "raw": data
        }

    @staticmethod
    def connected_pong(
        data: bytes
    ) -> dict | None:

        if len(data) < 8:
            return None

        bs = BitStream(data)
        receiver_ms = bs.read_uint32()
        sender_ms = bs.read_uint32()

        return {
            "receiver_ms": receiver_ms,
            "sender_ms": sender_ms,
            "raw": data
        }

    @staticmethod
    def disconnection_notification(
        data: bytes
    ) -> dict:

        reason = (
            data.decode(
                "ascii",
                errors="ignore"
            )
            if data else "No reason provided"
        )

        return {
            "reason": reason,
            "raw": data
        }

    @staticmethod
    def invalid_password(
        data: bytes
    ) -> dict:

        return {
            "raw": data
        }

    @staticmethod
    def vehicle_sync(
        data: bytes
    ) -> dict | None:

        bs = BitStream(data)

        player_id = bs.read_uint16()
        vehicle_id = bs.read_uint16()
        lr = bs.read_uint16()
        ud = bs.read_uint16()
        keys = bs.read_uint16()

        quat_cw_neg = bs.read_bool()
        quat_cx_neg = bs.read_bool()
        quat_cy_neg = bs.read_bool()
        quat_cz_neg = bs.read_bool()

        quat_cx = bs.read_uint16()
        quat_cy = bs.read_uint16()
        quat_cz = bs.read_uint16()

        qx = quat_cx / 65535.0
        qy = quat_cy / 65535.0
        qz = quat_cz / 65535.0
        if quat_cx_neg:
            qx = -qx
        if quat_cy_neg:
            qy = -qy
        if quat_cz_neg:
            qz = -qz
        qw = math.sqrt(max(0.0, 1.0 - qx * qx - qy * qy - qz * qz))
        if quat_cw_neg:
            qw = -qw

        x = bs.read_float()
        y = bs.read_float()
        z = bs.read_float()

        velocity_magnitude = bs.read_float()

        if velocity_magnitude != 0.0:
            speed_x = bs.read_uint16()
            speed_y = bs.read_uint16()
            speed_z = bs.read_uint16()

            velocity_x = (speed_x / 32767.5 - 1.0) * velocity_magnitude
            velocity_y = (speed_y / 32767.5 - 1.0) * velocity_magnitude
            velocity_z = (speed_z / 32767.5 - 1.0) * velocity_magnitude
        else:
            velocity_x = 0.0
            velocity_y = 0.0
            velocity_z = 0.0

        health = float(bs.read_uint16())

        health_nibble = bs.read_bits(4)
        armour_nibble = bs.read_bits(4)

        if health_nibble == 0x0F:
            player_health = 100
        elif health_nibble == 0x00:
            player_health = 0
        else:
            player_health = health_nibble * 7

        if armour_nibble == 0x0F:
            player_armour = 100
        elif armour_nibble == 0x00:
            player_armour = 0
        else:
            player_armour = armour_nibble * 7

        return {
            "packet_id": PacketID.SERVER_VEHICLE_SYNC,
            "player_id": player_id,
            "vehicle_id": vehicle_id,
            "lr": lr,
            "ud": ud,
            "keys": keys,
            "quat_w": qw,
            "quat_x": qx,
            "quat_y": qy,
            "quat_z": qz,
            "x": x,
            "y": y,
            "z": z,
            "velocity_x": velocity_x,
            "velocity_y": velocity_y,
            "velocity_z": velocity_z,
            "vehicle_health": health,
            "health": player_health,
            "armour": player_armour,
            "raw": data,
        }

    @staticmethod
    def passenger_sync(
        data: bytes
    ) -> dict | None:
        try:
            bs = BitStream(data)
            if bs.remaining_bits < 16:
                return None
            player_id = bs.read_uint16()
            if bs.remaining_bits < 24 * 8:
                pass
            vehicle_id = bs.read_uint16()
            drive_by = bs.read_bits(1)
            seat_flags = bs.read_bits(7)
            weapon = bs.read_uint8()
            health = bs.read_uint8()
            armour = bs.read_uint8()
            lr = bs.read_uint16()
            ud = bs.read_uint16()
            keys = bs.read_uint16()
            x = bs.read_float()
            y = bs.read_float()
            z = bs.read_float()
            return {
                "packet_id": PacketID.SERVER_PASSENGER_SYNC,
                "player_id": int(player_id),
                "vehicle_id": int(vehicle_id),
                "seat_id": int(seat_flags),
                "drive_by": int(drive_by),
                "weapon": int(weapon),
                "health": int(health),
                "armour": int(armour),
                "lr": int(lr),
                "ud": int(ud),
                "keys": int(keys),
                "x": float(x),
                "y": float(y),
                "z": float(z),
                "raw": data,
            }
        except EOFError:
            return None
        except Exception as e:
            logger.rpc_parse_error(f"passenger_sync parse error: {e}")
            return None

    @staticmethod
    def player_sync(
        data: bytes
    ) -> dict | None:
        try:
            bs = BitStream(data)
            if bs.remaining_bits < 16:
                return None
            player_id = bs.read_uint16()

            bHasLR = bs.read_bool()
            lr = bs.read_uint16() if bHasLR else 0

            bHasUD = bs.read_bool()
            ud = bs.read_uint16() if bHasUD else 0

            wKeys = bs.read_uint16()

            x = bs.read_float()
            y = bs.read_float()
            z = bs.read_float()

            cwNeg = bs.read_bool()
            cxNeg = bs.read_bool()
            cyNeg = bs.read_bool()
            czNeg = bs.read_bool()
            cx = bs.read_uint16()
            cy = bs.read_uint16()
            cz = bs.read_uint16()
            qx = cx / 65535.0
            qy = cy / 65535.0
            qz = cz / 65535.0
            if cxNeg:
                qx = -qx
            if cyNeg:
                qy = -qy
            if czNeg:
                qz = -qz
            diff = 1.0 - qx * qx - qy * qy - qz * qz
            if diff < 0.0:
                diff = 0.0
            qw = math.sqrt(diff)
            if cwNeg:
                qw = -qw

            hl = bs.read_bits(4)
            al = bs.read_bits(4)
            if hl == 0x0F:
                health = 100
            elif hl == 0:
                health = 0
            else:
                health = hl * 7
            if al == 0x0F:
                armour = 100
            elif al == 0:
                armour = 0
            else:
                armour = al * 7

            weapon = bs.read_uint8()
            special_action = bs.read_uint8()

            magnitude = bs.read_float()
            if magnitude != 0.0:
                sx = bs.read_uint16()
                sy = bs.read_uint16()
                sz = bs.read_uint16()
                vx = (sx / 32767.5 - 1.0) * magnitude
                vy = (sy / 32767.5 - 1.0) * magnitude
                vz = (sz / 32767.5 - 1.0) * magnitude
            else:
                vx = 0.0
                vy = 0.0
                vz = 0.0

            bHasSurf = bs.read_bool()
            if bHasSurf:
                wSurf = bs.read_uint16()
                surfX = bs.read_float()
                surfY = bs.read_float()
                surfZ = bs.read_float()
            else:
                wSurf = 0xFFFF
                surfX = 0.0
                surfY = 0.0
                surfZ = 0.0

            bHasAnim = bs.read_bool()
            if bHasAnim:
                anim = bs.read_int32()
            else:
                anim = 0

            return {
                "packet_id": PacketID.PLAYER_SYNC,
                "player_id": int(player_id),
                "lr": int(lr),
                "ud": int(ud),
                "keys": int(wKeys),
                "x": float(x),
                "y": float(y),
                "z": float(z),
                "quat_w": float(qw),
                "quat_x": float(qx),
                "quat_y": float(qy),
                "quat_z": float(qz),
                "health": int(health),
                "armour": int(armour),
                "weapon": int(weapon),
                "special_action": int(special_action),
                "velocity_x": float(vx),
                "velocity_y": float(vy),
                "velocity_z": float(vz),
                "has_surf": bool(bHasSurf),
                "surf_vehicle_id": int(wSurf),
                "surf_x": float(surfX),
                "surf_y": float(surfY),
                "surf_z": float(surfZ),
                "has_anim": bool(bHasAnim),
                "anim_id": int(anim),
                "raw": data,
            }
        except EOFError:
            return None
        except Exception as e:
            logger.rpc_parse_error(f"player_sync parse error: {e}")
            return None

    @staticmethod
    def rpc(
        data: bytes
    ) -> dict | None:

        parsed = RPC.read_rpc(data)

        if parsed is None:
            return None

        return {
            "rpc_id": parsed["rpc_id"],
            "payload": parsed["payload"],
            "parsed_payload": parsed["parsed_payload"],
            "raw": data
        }


PACKET_PARSE_REGISTRY: dict[str, tuple[int, "Callable[[bytes], dict | None]"]] = {
    "interface_sync": (PacketID.USER_INTERFACE_SYNC, parse_json_payload),
    "open_connection_reply": (
        PacketID.OPEN_CONNECTION_REPLY,
        PacketParser.open_connection_reply,
    ),
    "open_connection_cookie": (
        PacketID.OPEN_CONNECTION_COOKIE,
        PacketParser.open_connection_cookie,
    ),
    "auth_key": (
        PacketID.AUTH_KEY,
        PacketParser.auth_key,
    ),
    "connection_request_accepted": (
        PacketID.CONNECTION_REQUEST_ACCEPTED,
        PacketParser.connection_request_accepted,
    ),
    "invalid_password": (
        PacketID.INVALPASSWORD,
        PacketParser.invalid_password,
    ),
    "internal_ping": (
        PacketID.INTERNAL_PING,
        PacketParser.internal_ping,
    ),
    "connected_pong": (
        PacketID.CONNECTED_PONG,
        PacketParser.connected_pong,
    ),
    "disconnection_notification": (
        PacketID.DISCONNECTION_NOTIFICATION,
        PacketParser.disconnection_notification,
    ),
    "rpc": (
        PacketID.RPC,
        PacketParser.rpc,
    ),
    "player_sync": (
        PacketID.PLAYER_SYNC,
        PacketParser.player_sync,
    ),
    "vehicle_sync": (
        PacketID.SERVER_VEHICLE_SYNC,
        PacketParser.vehicle_sync,
    ),
    "passenger_sync": (
        PacketID.SERVER_PASSENGER_SYNC,
        PacketParser.passenger_sync,
    ),
}


PACKET_PARSERS = {
    packet_id: (name, parser)
    for name, (packet_id, parser) in PACKET_PARSE_REGISTRY.items()
}


def parse_packet(data: bytes) -> dict:

    if not data:
        return {"type": "unknown"}

    packet_id = data[0]

    entry = PACKET_PARSERS.get(packet_id)

    if entry is not None:
        packet_name, parser = entry
        result = parser(data[1:])

        if result is not None:
            result.setdefault("type", packet_name)
            result["packet_id"] = packet_id
            return result

    return {
        "type": "packet",
        "packet_id": packet_id,
        "data": data[1:]
    }
