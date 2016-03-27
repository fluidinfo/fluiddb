_fluidinfo()
{
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    opts="add-admin
          allocate-ebs
          attach-ebs
          bootstrap-database
          build-api-docs
          build-index
          check-integrity
          clear-cache
          create-user
          delete-index
          deploy
          help
          load-logs
          load-test-server
          load-trace-logs
          patch-database
          patch-status
          pull-logs
          report-error-summary
          report-error-tracebacks
          report-trace-log-summary
          snapshot-ebs
          update-index
          update-user
          update-version-tag
          version"
    COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
    return 0
}
complete -F _fluidinfo fluidinfo
