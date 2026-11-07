// Build helper: export ONE CE07929 protoboard-case component, assembled frame.
//   openscad -o parts/<name>.stl -D 'COMPONENT="base"' _ce_part.scad
// The placement literals mirror ce07929-case.scad: BAY_Y = 26.5,
// SEAT_Z = 4.4, ESP_X = -60, ESP_Y = 26.5, BOARD_TOP = 6.0.
COMPONENT = "base";
use <../../case/ce07929-case.scad>;

if      (COMPONENT == "base")   base();
else if (COMPONENT == "lid")    lid_local();
else if (COMPONENT == "board-") translate([0, -26.5, 4.4]) board();
else if (COMPONENT == "board+") translate([0,  26.5, 4.4]) board();
else if (COMPONENT == "esp32")  translate([-60, 26.5, 6.0]) esp32();
