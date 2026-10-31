--!nonstrict
local state = noctalia.expandPath("~/.local/state/media-capsule/")
local input = {session = noctalia.nowMs(), seq = 0, pressed = false, down_serial = 0, released_serial = 0, x = 0, y = 0}
local function send()
    input.seq = input.seq + 1
    noctalia.writeFile(state .. "panel-input.json", noctalia.json.encode(input))
end
function move(x,y) input.x,input.y=tonumber(x) or 0,tonumber(y) or 0 send() end
function down(x,y)
    input.pressed=true input.cancelled=false input.down_serial=input.down_serial+1
    input.down_x,input.down_y=tonumber(x) or 0,tonumber(y) or 0
    move(x,y)
end
function up(x,y)
    input.pressed=false input.up_x,input.up_y=tonumber(x) or 0,tonumber(y) or 0
    input.released_serial=input.down_serial move(x,y)
end
function cancel()
    if not input.pressed then return end
    input.pressed=false input.cancelled=true input.released_serial=input.down_serial send()
end
function onOpen()
    input.session=noctalia.nowMs() input.pressed=false send()
    noctalia.runAsync({"python3",noctalia.pluginDir() .. "/media_panel.py"})
    panel.render(ui.column({width=368,height=460,padding=0,radius=28,fill="#171a1f"},{
        ui.pixelStream({path=state .. "panel.sock",width=368,height=460,radius=28,
            onPointerDown="down",onPointerMove="move",onPointerUp="up",onPointerCancel="cancel"}),
    }))
end
function onClose() cancel() panel.render(ui.column({})) end
