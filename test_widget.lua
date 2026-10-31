local tree,stored
noctalia={
 expandPath=function(p) return p end,
 nowMs=function() return 10000 end,
 pluginDir=function() return '.' end,
 runAsync=function() end,
 getConfig=function() return nil end,
 getColor=function() return '#3388ee' end,
 writeFile=function(_,v) stored=v return true end,
 readFile=function() return 'status' end,
 json={encode=function(v) return v end,decode=function() return {width=227,updated=10,available=true} end},
 setUpdateInterval=function() end,
 togglePanel=function(id) assert(id=='pyrider3/media-capsule:controls') end,
}
ui=setmetatable({},{__index=function(_,tag) return function(props,children) return {tag=tag,props=props,children=children} end end})
barWidget={setVisible=function() end,render=function(v) tree=v end,setTooltip=function() end}
dofile('widget.luau')
assert(tree.props.gap==-227)
assert(tree.children[2].tag=='graph')
assert(tree.children[2].props.onPointerMove=='titleHover')
assert(tree.children[2].props.onPointerLeave=='titleLeave')
titleHover();assert(stored.hovered==true)
titleLeave();assert(stored.hovered==false)
onClick()
print('Native hover overlay, enter/leave and panel activation callbacks passed')
