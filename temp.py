from config import parse_config
from Database import Database

if __name__ == '__main__':
    # Load configuration file
    args = parse_config.parse_args("config/config.ini")
    print(args)

    db = Database(config=args, path=args['tuning_config']['knob_config'])

    db.get_all_pg_knobs()
