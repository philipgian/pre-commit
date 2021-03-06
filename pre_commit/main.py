from __future__ import unicode_literals

import argparse
import os
import sys

import pre_commit.constants as C
from pre_commit import color
from pre_commit import five
from pre_commit import git
from pre_commit.commands.autoupdate import autoupdate
from pre_commit.commands.clean import clean
from pre_commit.commands.install_uninstall import install
from pre_commit.commands.install_uninstall import install_hooks
from pre_commit.commands.install_uninstall import uninstall
from pre_commit.commands.run import run
from pre_commit.error_handler import error_handler
from pre_commit.logging_handler import add_logging_handler
from pre_commit.runner import Runner


# https://github.com/pre-commit/pre-commit/issues/217
# On OSX, making a virtualenv using pyvenv at . causes `virtualenv` and `pip`
# to install packages to the wrong place.  We don't want anything to deal with
# pyvenv
os.environ.pop('__PYVENV_LAUNCHER__', None)


def _add_color_option(parser):
    parser.add_argument(
        '--color', default='auto', type=color.use_color,
        metavar='{' + ','.join(color.COLOR_CHOICES) + '}',
        help='Whether to use color in output.  Defaults to `%(default)s`.',
    )


def _add_config_option(parser):
    parser.add_argument(
        '-c', '--config', default='.pre-commit-config.yaml',
        help='Path to alternate config file'
    )


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    argv = [five.to_text(arg) for arg in argv]
    parser = argparse.ArgumentParser()

    # http://stackoverflow.com/a/8521644/812183
    parser.add_argument(
        '-V', '--version',
        action='version',
        version='%(prog)s {}'.format(C.VERSION),
    )

    subparsers = parser.add_subparsers(dest='command')

    install_parser = subparsers.add_parser(
        'install', help='Install the pre-commit script.',
    )
    _add_color_option(install_parser)
    _add_config_option(install_parser)
    install_parser.add_argument(
        '-f', '--overwrite', action='store_true',
        help='Overwrite existing hooks / remove migration mode.',
    )
    install_parser.add_argument(
        '--install-hooks', action='store_true',
        help=(
            'Whether to install hook environments for all environments '
            'in the config file.'
        ),
    )
    install_parser.add_argument(
        '-t', '--hook-type', choices=('pre-commit', 'pre-push'),
        default='pre-commit',
    )
    install_parser.add_argument(
        '--allow-missing-config', action='store_true', default=False,
        help=(
            'Whether to allow a missing `pre-config` configuration file '
            'or exit with a failure code.'
        ),
    )

    install_hooks_parser = subparsers.add_parser(
        'install-hooks',
        help=(
            'Install hook environemnts for all environemnts in the config '
            'file.  You may find `pre-commit install --install-hooks` more '
            'useful.'
        ),
    )
    _add_color_option(install_hooks_parser)
    _add_config_option(install_hooks_parser)

    uninstall_parser = subparsers.add_parser(
        'uninstall', help='Uninstall the pre-commit script.',
    )
    _add_color_option(uninstall_parser)
    _add_config_option(uninstall_parser)
    uninstall_parser.add_argument(
        '-t', '--hook-type', choices=('pre-commit', 'pre-push'),
        default='pre-commit',
    )

    clean_parser = subparsers.add_parser(
        'clean', help='Clean out pre-commit files.',
    )
    _add_color_option(clean_parser)
    _add_config_option(clean_parser)
    autoupdate_parser = subparsers.add_parser(
        'autoupdate',
        help="Auto-update pre-commit config to the latest repos' versions.",
    )
    _add_color_option(autoupdate_parser)
    _add_config_option(autoupdate_parser)
    autoupdate_parser.add_argument(
        '--tags-only', action='store_true', help='Update to tags only.',
    )

    run_parser = subparsers.add_parser('run', help='Run hooks.')
    _add_color_option(run_parser)
    _add_config_option(run_parser)
    run_parser.add_argument('hook', nargs='?', help='A single hook-id to run')
    run_parser.add_argument(
        '--no-stash', default=False, action='store_true',
        help='Use this option to prevent auto stashing of unstaged files.',
    )
    run_parser.add_argument(
        '--verbose', '-v', action='store_true', default=False,
    )
    run_parser.add_argument(
        '--origin', '-o',
        help="The origin branch's commit_id when using `git push`.",
    )
    run_parser.add_argument(
        '--source', '-s',
        help="The remote branch's commit_id when using `git push`.",
    )
    run_parser.add_argument(
        '--allow-unstaged-config', default=False, action='store_true',
        help=(
            'Allow an unstaged config to be present.  Note that this will '
            'be stashed before parsing unless --no-stash is specified.'
        ),
    )
    run_parser.add_argument(
        '--hook-stage', choices=('commit', 'push'), default='commit',
        help='The stage during which the hook is fired e.g. commit or push.',
    )
    run_parser.add_argument(
        '--show-diff-on-failure', action='store_true',
        help='When hooks fail, run `git diff` directly afterward.',
    )
    run_mutex_group = run_parser.add_mutually_exclusive_group(required=False)
    run_mutex_group.add_argument(
        '--all-files', '-a', action='store_true', default=False,
        help='Run on all the files in the repo.  Implies --no-stash.',
    )
    run_mutex_group.add_argument(
        '--files', nargs='*', default=[],
        help='Specific filenames to run hooks on.',
    )

    help = subparsers.add_parser(
        'help', help='Show help for a specific command.',
    )
    help.add_argument('help_cmd', nargs='?', help='Command to show help for.')

    # Argparse doesn't really provide a way to use a `default` subparser
    if len(argv) == 0:
        argv = ['run']
    args = parser.parse_args(argv)
    if args.command == 'run':
        args.files = [
            os.path.relpath(os.path.abspath(filename), git.get_root())
            for filename in args.files
        ]

    if args.command == 'help':
        if args.help_cmd:
            parser.parse_args([args.help_cmd, '--help'])
        else:
            parser.parse_args(['--help'])

    with error_handler():
        add_logging_handler(args.color)
        runner = Runner.create(args.config)
        git.check_for_cygwin_mismatch()

        if args.command == 'install':
            return install(
                runner, overwrite=args.overwrite, hooks=args.install_hooks,
                hook_type=args.hook_type,
                skip_on_missing_conf=args.allow_missing_config,
            )
        elif args.command == 'install-hooks':
            return install_hooks(runner)
        elif args.command == 'uninstall':
            return uninstall(runner, hook_type=args.hook_type)
        elif args.command == 'clean':
            return clean(runner)
        elif args.command == 'autoupdate':
            return autoupdate(runner, args.tags_only)
        elif args.command == 'run':
            return run(runner, args)
        else:
            raise NotImplementedError(
                'Command {} not implemented.'.format(args.command)
            )

        raise AssertionError(
            'Command {} failed to exit with a returncode'.format(args.command)
        )


if __name__ == '__main__':
    exit(main())
