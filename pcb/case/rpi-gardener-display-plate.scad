// RPi Gardener Display Plate
// Top plate for mounting OLED screens and LCD 1602A above the HAT
// Export to STL: OpenSCAD -> File -> Export -> STL

/* [Base Dimensions] */
// Extended depth to accommodate LCD 1602A below OLEDs
base_width = 90;          // mm
base_depth = 95;          // mm - sized to fit LCD 1602A below OLEDs
base_thickness = 1.5;     // mm
corner_radius = 3;        // mm

/* [Mounting Holes - RPi/HAT Pattern] */
// Standard RPi 4 mounting pattern: 58mm x 49.5mm
// Positioned toward the top of the extended plate
hole_spacing_x = 58;      // mm between holes horizontally
hole_spacing_y = 49.5;    // mm between holes vertically
hole_diameter = 3.2;      // mm - M3 clearance hole
// Match PCB hole positions from the right edge
hole_offset_x = base_width - hole_spacing_x - 3.5;  // mm from left (3.5mm from right edge)
hole_offset_y = base_depth - hole_spacing_y - 4;    // near top (4mm from top edge, avoids OLED/cable slots)

/* [OLED Display Configuration] */
// Number of OLED displays: 1 = single centered, 2 = dual side by side
oled_count = 2;

// OLED type: 0 = Custom, 1 = 0.96" OLED (SSD1306), 2 = 1.3" OLED
oled_type = 1;

// Gap between OLED displays when using dual mode (mm)
oled_gap = 6;

// OLED vertical position from top edge (mm)
oled_offset_from_top = 22;

/* [LCD 1602A Configuration] */
// Enable LCD 1602A mounting
lcd_1602_enabled = true;

// LCD 1602A dimensions (standard module ~80x36mm, screen with bezel ~72x24mm)
lcd_1602_cutout = [73, 25];           // Display window (with 1mm margin)
lcd_1602_mount_spacing = [75, 31];    // Mounting hole spacing
lcd_1602_module_size = [80, 36];      // Full module size

// LCD vertical position from bottom edge (mm)
lcd_offset_from_bottom = 4;


/* [Cable Routing Slots] */
// Slots at the top for sensor cables (DHT22, moisture sensors, etc.)
cable_slots_enabled = true;
cable_slot_count = 3;         // Number of slots
cable_slot_width = 20;        // mm - width of each slot
cable_slot_height = 5;        // mm - height of each slot
cable_slot_spacing = 8;       // mm - gap between slots
cable_slot_from_top = 12;     // mm - positioned between mounting holes and OLEDs

/* [DHT22 Holder Configuration] */
// Vertical tab mount for DHT22 sensor module (screw-mounted)
dht22_holder_enabled = true;
dht22_tab_width = 16;         // mm - width of the tab
dht22_tab_height = 35;        // mm - height of tab above plate
dht22_tab_thickness = 3;      // mm - thickness of the tab
dht22_hole_diameter = 3.2;    // mm - M3 clearance hole for screw
dht22_hole_height = 28;       // mm - height of hole center from plate surface


/* [Custom OLED Cutout] */
// Only used when oled_type = 0
custom_cutout_width = 30;   // mm
custom_cutout_height = 15;  // mm

/* [Display Module Mounting] */
display_mount_holes = true;
oled_mount_hole_diameter = 2.2;   // mm - M2 clearance for OLEDs
lcd_mount_hole_diameter = 3.2;    // mm - M3 clearance for 1602A

// OLED presets
oled_096_cutout = [26, 15];
oled_096_mount_spacing = [23.5, 22.5];
oled_096_mount_y_offset = -1.25;    // mm - bottom holes 5mm from cutout, top holes 2.5mm from cutout
oled_096_module_size = [27, 27];

oled_13_cutout = [32, 18];
oled_13_mount_spacing = [29, 27];
oled_13_mount_y_offset = 0;
oled_13_module_size = [35, 33];

// Get OLED dimensions based on type
function get_oled_cutout() =
    oled_type == 1 ? oled_096_cutout :
    oled_type == 2 ? oled_13_cutout :
    [custom_cutout_width, custom_cutout_height];

function get_oled_mount_spacing() =
    oled_type == 1 ? oled_096_mount_spacing :
    oled_type == 2 ? oled_13_mount_spacing :
    [custom_cutout_width + 6, custom_cutout_height + 6];

function get_oled_mount_y_offset() =
    oled_type == 1 ? oled_096_mount_y_offset :
    oled_type == 2 ? oled_13_mount_y_offset :
    0;

function get_oled_module_size() =
    oled_type == 1 ? oled_096_module_size :
    oled_type == 2 ? oled_13_module_size :
    [custom_cutout_width + 6, custom_cutout_height + 6];

// Modules
module rounded_rect(w, d, h, r) {
    hull() {
        translate([r, r, 0]) cylinder(h=h, r=r, $fn=32);
        translate([w-r, r, 0]) cylinder(h=h, r=r, $fn=32);
        translate([r, d-r, 0]) cylinder(h=h, r=r, $fn=32);
        translate([w-r, d-r, 0]) cylinder(h=h, r=r, $fn=32);
    }
}

module rounded_cutout(w, h, thickness, r=2) {
    hull() {
        translate([r, r, 0]) cylinder(h=thickness, r=r, $fn=16);
        translate([w-r, r, 0]) cylinder(h=thickness, r=r, $fn=16);
        translate([r, h-r, 0]) cylinder(h=thickness, r=r, $fn=16);
        translate([w-r, h-r, 0]) cylinder(h=thickness, r=r, $fn=16);
    }
}

// OLED display cutout and mounting holes
module oled_cutout_and_mount(center_x, center_y, cutout, mount_spacing, mount_y_offset=0) {
    // Display cutout
    translate([center_x - cutout[0]/2, center_y - cutout[1]/2, -0.1])
        rounded_cutout(cutout[0], cutout[1], base_thickness + 0.2);

    // Mounting holes (M2)
    if (display_mount_holes) {
        for (dx = [-1, 1]) {
            for (dy = [-1, 1]) {
                translate([
                    center_x + dx * mount_spacing[0] / 2,
                    center_y + dy * mount_spacing[1] / 2 + mount_y_offset,
                    -0.1
                ])
                cylinder(h=base_thickness+0.2, d=oled_mount_hole_diameter, $fn=32);
            }
        }
    }
}

// Cable routing slot
module cable_slot(width, height) {
    hull() {
        translate([0, 0, 0]) cylinder(h=base_thickness+0.2, d=height, $fn=16);
        translate([width, 0, 0]) cylinder(h=base_thickness+0.2, d=height, $fn=16);
    }
}

// DHT22 vertical tab mount with screw hole
// Flat tab extends from top edge, hole on the vertical face
module dht22_holder() {
    tab_x = base_width / 2 - dht22_tab_width / 2;

    difference() {
        // Vertical tab
        translate([tab_x, base_depth - dht22_tab_thickness, 0])
            cube([dht22_tab_width, dht22_tab_thickness, dht22_tab_height]);

        // Screw hole through the face (horizontal, pointing outward)
        translate([base_width / 2, base_depth + 0.1, dht22_hole_height])
            rotate([90, 0, 0])
            cylinder(h=dht22_tab_thickness + 0.2, d=dht22_hole_diameter, $fn=24);
    }
}


// LCD 1602A cutout and mounting holes
module lcd_1602_cutout_and_mount(center_x, center_y) {
    // Display window cutout
    translate([center_x - lcd_1602_cutout[0]/2, center_y - lcd_1602_cutout[1]/2, -0.1])
        rounded_cutout(lcd_1602_cutout[0], lcd_1602_cutout[1], base_thickness + 0.2, r=1);

    // Mounting holes (M3) at corners
    if (display_mount_holes) {
        for (dx = [-1, 1]) {
            for (dy = [-1, 1]) {
                translate([
                    center_x + dx * lcd_1602_mount_spacing[0] / 2,
                    center_y + dy * lcd_1602_mount_spacing[1] / 2,
                    -0.1
                ])
                cylinder(h=base_thickness+0.2, d=lcd_mount_hole_diameter, $fn=32);
            }
        }
    }
}


// Main assembly - flat display plate
module display_plate() {
    oled_cutout = get_oled_cutout();
    oled_mount_spacing = get_oled_mount_spacing();
    oled_mount_y_offset = get_oled_mount_y_offset();
    oled_module_size = get_oled_module_size();
    center_x = base_width / 2;
    oled_center_y = base_depth - oled_offset_from_top - oled_module_size[1] / 2;
    lcd_center_y = lcd_offset_from_bottom + lcd_1602_module_size[1] / 2;
    oled_dual_offset = (oled_module_size[0] + oled_gap) / 2;

    difference() {
        // Flat plate with rounded corners
        rounded_rect(base_width, base_depth, base_thickness, corner_radius);

        // RPi/HAT mounting holes (M3)
        translate([hole_offset_x, hole_offset_y, -0.1])
            cylinder(h=base_thickness+0.2, d=hole_diameter, $fn=32);
        translate([hole_offset_x + hole_spacing_x, hole_offset_y, -0.1])
            cylinder(h=base_thickness+0.2, d=hole_diameter, $fn=32);
        translate([hole_offset_x, hole_offset_y + hole_spacing_y, -0.1])
            cylinder(h=base_thickness+0.2, d=hole_diameter, $fn=32);
        translate([hole_offset_x + hole_spacing_x, hole_offset_y + hole_spacing_y, -0.1])
            cylinder(h=base_thickness+0.2, d=hole_diameter, $fn=32);

        // OLED cutouts and mounting holes
        if (oled_count == 1) {
            oled_cutout_and_mount(center_x, oled_center_y, oled_cutout, oled_mount_spacing, oled_mount_y_offset);
        } else {
            oled_cutout_and_mount(center_x - oled_dual_offset, oled_center_y, oled_cutout, oled_mount_spacing, oled_mount_y_offset);
            oled_cutout_and_mount(center_x + oled_dual_offset, oled_center_y, oled_cutout, oled_mount_spacing, oled_mount_y_offset);
        }

        // LCD 1602A cutout and mounting holes
        if (lcd_1602_enabled) {
            lcd_1602_cutout_and_mount(center_x, lcd_center_y);
        }

        // Cable routing slots at top
        if (cable_slots_enabled) {
            total_slots_width = cable_slot_count * cable_slot_width + (cable_slot_count - 1) * cable_slot_spacing;
            slot_start_x = (base_width - total_slots_width) / 2;
            slot_y = base_depth - cable_slot_from_top - cable_slot_height / 2;

            for (i = [0:cable_slot_count-1]) {
                translate([slot_start_x + i * (cable_slot_width + cable_slot_spacing), slot_y, -0.1])
                    cable_slot(cable_slot_width, cable_slot_height);
            }
        }
    }

    // DHT22 holder
    if (dht22_holder_enabled) {
        dht22_holder();
    }
}

// Render the plate
display_plate();

// Info
oled_cutout = get_oled_cutout();
oled_module_size = get_oled_module_size();
oled_names = ["Custom", "0.96\" OLED (SSD1306)", "1.3\" OLED"];

echo("=== RPi Gardener Display Plate ===");
echo(str("Base size: ", base_width, "mm x ", base_depth, "mm x ", base_thickness, "mm"));
echo("");
echo("OLED Section (top):");
echo(str("  Count: ", oled_count));
echo(str("  Type: ", oled_names[oled_type]));
echo(str("  Cutout: ", oled_cutout[0], "mm x ", oled_cutout[1], "mm"));
if (oled_count == 2) {
    echo(str("  Gap: ", oled_gap, "mm"));
    echo(str("  Total width: ", oled_module_size[0] * 2 + oled_gap, "mm"));
}
echo("");
if (lcd_1602_enabled) {
    echo("LCD 1602A Section (bottom):");
    echo(str("  Cutout: ", lcd_1602_cutout[0], "mm x ", lcd_1602_cutout[1], "mm"));
    echo(str("  Mount spacing: ", lcd_1602_mount_spacing[0], "mm x ", lcd_1602_mount_spacing[1], "mm"));
}
echo("");
if (cable_slots_enabled) {
    echo("Cable Routing Slots (top edge):");
    echo(str("  Count: ", cable_slot_count));
    echo(str("  Slot size: ", cable_slot_width, "mm x ", cable_slot_height, "mm"));
    echo(str("  Spacing: ", cable_slot_spacing, "mm"));
}
echo("");
if (dht22_holder_enabled) {
    echo("DHT22 Mount Tab (top edge, centered):");
    echo(str("  Tab size: ", dht22_tab_width, "mm x ", dht22_tab_height, "mm x ", dht22_tab_thickness, "mm"));
    echo(str("  Screw hole: ", dht22_hole_diameter, "mm (M3) at ", dht22_hole_height, "mm height"));
}
echo("");
echo("Assembly:");
echo("1. Stack on top of HAT using M3 screws and spacers");
echo("2. Mount OLED module(s) using M2.5 screws");
echo("3. Mount LCD 1602A using M3 screws");
echo("4. Screw DHT22 module onto the post using M3 screw");
echo("5. Route sensor wires through top slots to HAT connectors");
