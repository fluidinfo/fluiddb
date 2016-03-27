all: benchmark

benchmark:
	@if [ -z "${GRINDER_HOME}" ]; then \
		echo "Please setup your GRINDER_HOME environment variable." >&2; \
		exit 1; \
	fi

	@if [ -z "${JYTHON_HOME}" ]; then \
		echo "Please setup your JYTHON_HOME environment variable." >&2; \
		exit 2; \
	fi

	java \
		-Dgrinder.jvm.arguments="-Dpython.home=${JYTHON_HOME}" \
		-cp ${GRINDER_HOME}/lib/grinder.jar \
		net.grinder.Grinder \
		main.properties

clean:
	rm -rf *.log*
	rm -rf *.class

