import argparse
from importlib.resources import files

from .channel_deviation_view import run_app
from .reactor_utils import estimate_output, reactor_stats, render_ascii_map, rod_type_table


def build_parser():
    parser = argparse.ArgumentParser(
        prog="helios-core",
        description="RBMK reactor control station and utilities",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("gui", help="Launch the reactor control station GUI")

    map_parser = subparsers.add_parser("map", help="Print reactor core layout map")
    map_parser.add_argument(
        "--show-placeholders",
        action="store_true",
        help="Show placeholder cells as P instead of .",
    )

    subparsers.add_parser("stats", help="Show reactor grid statistics")
    subparsers.add_parser("rod-types", help="List rod type codes and meanings")

    estimate_parser = subparsers.add_parser("estimate", help="Estimate output from power percent")
    estimate_parser.add_argument("power", type=float, help="Core power percent")

    guide_parser = subparsers.add_parser("guide", help="Show operator guide path or content")
    guide_parser.add_argument("--print", action="store_true", dest="print_guide", help="Print guide text")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in (None, "gui"):
        run_app()
        return

    if args.command == "map":
        print(render_ascii_map(show_placeholder=args.show_placeholders))
        return

    if args.command == "stats":
        stats = reactor_stats()
        print(f"Active positions: {stats['active_positions']}/{stats['total_positions']} ({stats['utilization_percent']:.1f}%)")
        for rod_code, count in sorted(stats["counts"].items()):
            print(f"{rod_code}: {count}")
        return

    if args.command == "rod-types":
        print(rod_type_table())
        return

    if args.command == "estimate":
        thermal_mw, electric_mw = estimate_output(args.power)
        print(f"Thermal output: {thermal_mw:.1f} MW")
        print(f"Electrical output: {electric_mw:.1f} MW")
        return

    if args.command == "guide":
        guide_path = files("helios_core").joinpath("resources/OPERATOR_GUIDE.txt")
        if args.print_guide:
            print(guide_path.read_text(encoding="utf-8"))
        else:
            print(str(guide_path))
        return
