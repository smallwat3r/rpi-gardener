// RPi Gardener HAT Base
// Flat base with M3 holes for RPi 4 and HAT mounting with spacers
// Export to STL: OpenSCAD -> File -> Export -> STL

/* [Base Dimensions] */
// Base sized to support full Raspberry Pi 4 (85mm x 56mm)
base_width = 90;          // mm - slightly larger than Pi for margin
base_depth = 62;          // mm - slightly larger than Pi for margin
base_thickness = 2;       // mm
corner_radius = 3;        // mm

/* [Mounting Holes] */
// Standard RPi 4 mounting pattern: 58mm x 49mm
// Holes are 3.5mm from board edges on the Pi
// Same holes work for both RPi and HAT (they align)
hole_spacing_x = 58;      // mm between holes horizontally
hole_spacing_y = 49;      // mm between holes vertically
hole_diameter = 3.2;      // mm - M3 clearance hole
// Center the Pi mounting pattern on the base
hole_offset_x = (90 - 58) / 2;   // 16mm - centered on base width
hole_offset_y = (62 - 49) / 2;   // 6.5mm - centered on base depth

/* [Ventilation] */
vent_slots = true;        // Add ventilation slots
vent_width = 3;           // mm
vent_length = 50;         // mm - longer to match wider base
vent_count = 6;           // more slots for better cooling

/* [Cable Cutout] */
usb_cutout = true;        // Cutout for USB/power cables
usb_cutout_width = 25;    // mm
usb_cutout_depth = 10;    // mm

// Modules
module rounded_rect(w, d, h, r) {
    hull() {
        translate([r, r, 0]) cylinder(h=h, r=r, $fn=32);
        translate([w-r, r, 0]) cylinder(h=h, r=r, $fn=32);
        translate([r, d-r, 0]) cylinder(h=h, r=r, $fn=32);
        translate([w-r, d-r, 0]) cylinder(h=h, r=r, $fn=32);
    }
}

module vent_slot(length, width) {
    hull() {
        translate([0, 0, 0]) cylinder(h=base_thickness+0.2, d=width, $fn=16);
        translate([length, 0, 0]) cylinder(h=base_thickness+0.2, d=width, $fn=16);
    }
}

// Main assembly
module base() {
    difference() {
        // Base plate
        rounded_rect(base_width, base_depth, base_thickness, corner_radius);

        // Mounting holes (M3) - same positions for RPi and HAT
        // Hole 1 (H1 position)
        translate([hole_offset_x, hole_offset_y, -0.1])
            cylinder(h=base_thickness+0.2, d=hole_diameter, $fn=32);

        // Hole 2 (H2 position)
        translate([hole_offset_x + hole_spacing_x, hole_offset_y, -0.1])
            cylinder(h=base_thickness+0.2, d=hole_diameter, $fn=32);

        // Hole 3 (H3 position)
        translate([hole_offset_x, hole_offset_y + hole_spacing_y, -0.1])
            cylinder(h=base_thickness+0.2, d=hole_diameter, $fn=32);

        // Hole 4 (H4 position)
        translate([hole_offset_x + hole_spacing_x, hole_offset_y + hole_spacing_y, -0.1])
            cylinder(h=base_thickness+0.2, d=hole_diameter, $fn=32);

        // Ventilation slots
        if (vent_slots) {
            slot_start_x = (base_width - vent_length) / 2;
            slot_spacing = (base_depth - 20) / (vent_count + 1);
            for (i = [1:vent_count]) {
                translate([slot_start_x, 10 + i * slot_spacing, -0.1])
                    vent_slot(vent_length, vent_width);
            }
        }

        // USB/Power cable cutout
        if (usb_cutout) {
            translate([base_width - usb_cutout_depth + 1, (base_depth - usb_cutout_width) / 2, -0.1])
                cube([usb_cutout_depth + 1, usb_cutout_width, base_thickness + 0.2]);
        }
    }
}

// Render the base
base();

// Info
echo("=== RPi Gardener HAT Base ===");
echo(str("Base size: ", base_width, "mm x ", base_depth, "mm x ", base_thickness, "mm"));
echo(str("Supports: Raspberry Pi 4 (85mm x 56mm)"));
echo(str("Hole pattern: ", hole_spacing_x, "mm x ", hole_spacing_y, "mm (standard RPi)"));
echo(str("Hole positions: (", hole_offset_x, ",", hole_offset_y, ") to (", hole_offset_x+hole_spacing_x, ",", hole_offset_y+hole_spacing_y, ")"));
echo(str("Hole diameter: ", hole_diameter, "mm (M3 clearance)"));
echo("");
echo("Assembly with spacers:");
echo("1. Insert M3 screws from bottom through base holes");
echo("2. Add spacer (e.g. 5-6mm) for RPi clearance");
echo("3. Mount Raspberry Pi 4 (center on base)");
echo("4. Add spacer (e.g. 10-12mm) for HAT clearance");
echo("5. Mount HAT");
echo("6. Secure with M3 nuts on top");
