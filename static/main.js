document.addEventListener('DOMContentLoaded', function() {
    // --- Selectores Globales ---
    const views = {
        participantes: document.getElementById('view-participantes'),
        generador: document.getElementById('view-generador'),
        historial: document.getElementById('view-historial')
    };
    const navLinks = {
        participantes: document.getElementById('nav-participantes'),
        generador: document.getElementById('nav-generador'),
        historial: document.getElementById('nav-historial')
    };

    // --- Navegación Principal ---
    function switchView(viewName) {
        Object.values(views).forEach(view => view.classList.add('hidden'));
        Object.values(navLinks).forEach(link => link.classList.remove('active'));

        views[viewName].classList.remove('hidden');
        navLinks[viewName].classList.add('active');
    }

    navLinks.participantes.addEventListener('click', (e) => { e.preventDefault(); switchView('participantes'); });
    navLinks.generador.addEventListener('click', (e) => { e.preventDefault(); switchView('generador'); });
    navLinks.historial.addEventListener('click', (e) => {
        e.preventDefault();
        switchView('historial');
        loadHistory();
    });

    function loadHistory() {
        const historyBody = document.getElementById('history-table-body');
        historyBody.innerHTML = '<tr><td colspan="3">Cargando...</td></tr>';

        fetch('/api/history')
            .then(res => res.json())
            .then(data => {
                historyBody.innerHTML = '';
                if (data.length === 0) {
                    historyBody.innerHTML = '<tr><td colspan="3">No hay historial guardado.</td></tr>';
                    return;
                }
                data.forEach(row => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${row.anio}-${String(row.mes).padStart(2, '0')}-S${row.semana}</td>
                        <td>${row.asignacion_nombre}</td>
                        <td>${row.nombre}</td>
                    `;
                    historyBody.appendChild(tr);
                });
            });
    }

    // --- Lógica de Gestión de Participantes ---
    const rolesList = document.getElementById('roles-list');
    const roleManagementSection = document.getElementById('role-management-section');
    const welcomeMessage = document.getElementById('welcome-message');
    const currentRoleTitle = document.getElementById('current-role-title');
    const currentRoleIdInput = document.getElementById('current-role-id');
    const participantListUl = document.getElementById('participant-list-ul');
    const addPersonForm = document.getElementById('add-person-form');

    // Opciones especiales
    const smmOptions = document.getElementById('smm-options');
    const acomodadoresOptions = document.getElementById('acomodadores-options');

    // --- Carga inicial de Roles ---
    fetch('/api/roles')
        .then(response => response.json())
        .then(roles => {
            rolesList.innerHTML = ''; // Limpiar lista
            roles.forEach(rol => {
                const li = document.createElement('li');
                li.textContent = rol.nombre_rol;
                li.dataset.id = rol.id;
                li.dataset.nombre = rol.nombre_rol;
                li.classList.add('role-item');
                rolesList.appendChild(li);
            });
        });

    // --- Event Listener para seleccionar un Rol ---
    rolesList.addEventListener('click', (event) => {
        if (event.target && event.target.matches('li.role-item')) {
            const roleId = event.target.dataset.id;
            const roleName = event.target.dataset.nombre;

            // Marcar rol activo
            document.querySelectorAll('.role-item').forEach(item => item.classList.remove('active'));
            event.target.classList.add('active');

            loadParticipantsForRole(roleId, roleName);
        }
    });

    // --- Cargar participantes para un rol ---
    function loadParticipantsForRole(roleId, roleName) {
        welcomeMessage.classList.add('hidden');
        roleManagementSection.classList.remove('hidden');

        currentRoleTitle.textContent = `Gestionar: ${roleName}`;
        currentRoleIdInput.value = roleId;

        // Mostrar/ocultar opciones especiales
        smmOptions.classList.toggle('hidden', roleName.toLowerCase() !== 'seamos mejores maestros');
        acomodadoresOptions.classList.toggle('hidden', roleName.toLowerCase() !== 'acomodadores');

        // Cargar la lista de participantes
        fetch(`/api/roles/${roleId}/personas`)
            .then(response => response.json())
            .then(personas => {
                participantListUl.innerHTML = '';
                if (personas.length === 0) {
                    participantListUl.innerHTML = '<li>No hay participantes en este rol.</li>';
                } else {
                    personas.forEach(persona => {
                        const li = document.createElement('li');
                        let details = '';
                        if (persona.genero) details += ` (${persona.genero})`;
                        if (persona.grupo_edad) details += ` (${persona.grupo_edad})`;

                        li.innerHTML = `${persona.nombre} ${details} <button class="delete-btn" data-persona-id="${persona.id}" data-rol-id="${roleId}">Eliminar</button>`;
                        participantListUl.appendChild(li);
                    });
                }
            });
    }

    // --- Event Listener para añadir personas ---
    addPersonForm.addEventListener('submit', function(event) {
        event.preventDefault();
        const formData = new FormData(this);
        const roleId = currentRoleIdInput.value;
        const roleName = document.querySelector('.role-item.active').dataset.nombre;

        const data = {
            nombres: formData.get('nombres').split('\n').map(n => n.trim()).filter(n => n),
            rol_id: roleId,
            genero: roleName.toLowerCase() === 'seamos mejores maestros' ? formData.get('genero') : null,
            grupo_edad: roleName.toLowerCase() === 'acomodadores' ? formData.get('grupo_edad') : null,
        };

        fetch('/api/personas', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                loadParticipantsForRole(roleId, roleName); // Recargar lista
                addPersonForm.reset(); // Limpiar formulario
            } else {
                alert('Error al añadir participante(s): ' + (result.errors || 'Error desconocido'));
            }
        });
    });

    // --- Event Listener para eliminar una persona ---
    participantListUl.addEventListener('click', function(event) {
        if (event.target && event.target.matches('button.delete-btn')) {
            const personaId = event.target.dataset.personaId;
            const roleId = event.target.dataset.rolId;
            const roleName = document.querySelector('.role-item.active').dataset.nombre;

            if (confirm('¿Estás seguro de que quieres eliminar a este participante de este rol?')) {
                fetch(`/api/personas/${personaId}/roles/${roleId}`, {
                    method: 'DELETE'
                })
                .then(response => response.json())
                .then(result => {
                    if (result.success) {
                        loadParticipantsForRole(roleId, roleName); // Recargar lista
                    } else {
                        alert('Error al eliminar: ' + result.message);
                    }
                });
            }
        }
    });

    // --- Lógica del Generador de Programa ---
    const monthInput = document.getElementById('month-input');
    const weeklyConfigContainer = document.getElementById('weekly-config-container');
    const generateScheduleBtn = document.getElementById('generate-schedule-btn');

    monthInput.addEventListener('change', function() {
        const [year, month] = this.value.split('-').map(Number);
        if (!year || !month) return;

        weeklyConfigContainer.innerHTML = ''; // Limpiar configs anteriores
        generateScheduleBtn.classList.remove('hidden');

        const weeks = getWeeksForMonth(year, month);

        weeks.forEach((week, index) => {
            const weekDiv = document.createElement('div');
            weekDiv.classList.add('week-config', 'card');
            weekDiv.innerHTML = `
                <h4>Semana ${index + 1} (Inicia Lunes ${week.getDate()})</h4>
                <div class="form-group">
                    <label>Número de partes de "Seamos Mejores Maestros":</label>
                    <input type="number" class="smm-parts-count" min="1" max="4" value="3" data-week-index="${index}">
                </div>
                <div id="smm-config-week-${index}" class="smm-config-container">
                    <!-- Config SMM se genera aquí -->
                </div>
                <div class="form-group">
                    <label>Otras Asignaciones:</label>
                    <div class="checkbox-group">
                        <input type="checkbox" id="vym2-week-${index}" name="vym2_presente" checked>
                        <label for="vym2-week-${index}">Incluir "Vida y Ministerio 2"</label>
                    </div>
                    <div class="checkbox-group">
                        <input type="checkbox" id="vym3-week-${index}" name="vym3_presente" checked>
                        <label for="vym3-week-${index}">Incluir "Vida y Ministerio 3"</label>
                    </div>
                </div>
            `;
            weeklyConfigContainer.appendChild(weekDiv);

            // Generar la configuración inicial para SMM
            const smmCountInput = weekDiv.querySelector('.smm-parts-count');
            generateSmmConfig(index, parseInt(smmCountInput.value));

            // Añadir listener para cuando cambia el número de partes
            smmCountInput.addEventListener('change', (e) => {
                generateSmmConfig(index, parseInt(e.target.value));
            });
        });
    });

    function generateSmmConfig(weekIndex, count) {
        const container = document.getElementById(`smm-config-week-${weekIndex}`);
        container.innerHTML = '';
        for (let i = 1; i <= count; i++) {
            container.innerHTML += `
                <div class="smm-part-config">
                    <label>Mejores Maestros ${i}:</label>
                    <select name="smm_${i}_tipo">
                        <option value="persona_sola">Una persona</option>
                        <option value="demostracion">Demostración (2)</option>
                    </select>
                    <select name="smm_${i}_genero">
                        <option value="hombre">Hombres</option>
                        <option value="mujer">Mujeres</option>
                    </select>
                </div>
            `;
        }
    }

    function getWeeksForMonth(year, month) {
        const weeks = [];
        const date = new Date(Date.UTC(year, month - 1, 1));

        // Ir al primer Lunes del mes o el último lunes del mes anterior si el mes no empieza en lunes
        while (date.getUTCDay() !== 1) {
            date.setUTCDate(date.getUTCDate() - 1);
        }

        // Si el lunes encontrado es del mes anterior, avanzar a la siguiente semana
        if (date.getUTCMonth() !== month - 1) {
             date.setUTCDate(date.getUTCDate() + 7);
        }

        // Recorrer todas las semanas del mes
        while (date.getUTCMonth() === month - 1) {
            weeks.push(new Date(date));
            date.setUTCDate(date.getUTCDate() + 7);
        }
        return weeks;
    }

    // --- Lógica para Recopilar y Enviar Datos del Generador ---
    generateScheduleBtn.addEventListener('click', function() {
        const [year, month] = monthInput.value.split('-').map(Number);
        const weeklyConfigs = [];
        const weekElements = document.querySelectorAll('.week-config');

        weekElements.forEach((weekEl, index) => {
            const config = {
                week_index: index,
                smm_count: weekEl.querySelector('.smm-parts-count').value,
                vym2_presente: weekEl.querySelector(`input[name="vym2_presente"]`).checked,
                vym3_presente: weekEl.querySelector(`input[name="vym3_presente"]`).checked,
            };

            const smmParts = weekEl.querySelectorAll('.smm-part-config');
            smmParts.forEach((partEl, i) => {
                config[`smm_part_${i+1}`] = {
                    tipo: partEl.querySelector(`select[name="smm_${i+1}_tipo"]`).value,
                    genero: partEl.querySelector(`select[name="smm_${i+1}_genero"]`).value,
                };
            });
            weeklyConfigs.push(config);
        });

        const fullConfig = {
            year: year,
            month: month,
            weeks: weeklyConfigs
        };

        // Enviar al backend
        fetch('/api/generate_schedule', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(fullConfig)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Error del servidor: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            displaySchedule(data);
        })
        .catch(error => {
            console.error('Error al generar el programa:', error);
            alert('Ocurrió un error al generar el programa. Asegúrate de que hay suficientes participantes para todas las asignaciones. Para más detalles, revisa la consola del navegador (F12).');
        });
    });

    function displaySchedule(scheduleData) {
        const outputDiv = document.getElementById('schedule-output');
        outputDiv.innerHTML = '';
        outputDiv.classList.remove('hidden');

        if (scheduleData.weeks && scheduleData.weeks.length > 0) {
            scheduleData.weeks.forEach(week => {
                const weekCard = document.createElement('div');
                weekCard.classList.add('schedule-week', 'card');

                const assignmentsContainer = document.createElement('div');
                assignmentsContainer.classList.add('assignments-list');

                week.assignments.forEach(a => {
                    const row = document.createElement('div');
                    row.classList.add('assignment-row');

                    const titleEl = document.createElement('strong');
                    titleEl.classList.add('assignment-title');
                    titleEl.textContent = `${a.title}:`;

                    const namesEl = document.createElement('span');
                    namesEl.classList.add('assignment-names');
                    a.slots.forEach((slot, index) => {
                        const nameSpan = document.createElement('span');
                        nameSpan.classList.add('assignee');
                        nameSpan.textContent = slot.nombre;
                        nameSpan.dataset.slotKey = slot.key;
                        nameSpan.dataset.personId = slot.persona_id;
                        nameSpan.dataset.weekIndex = week.week_index;
                        namesEl.appendChild(nameSpan);

                        // Usar '/' para SMM, ',' para los demás
                        if (index < a.slots.length - 1) {
                            const separator = a.title.includes('Mejores Maestros') ? ' / ' : ', ';
                            namesEl.appendChild(document.createTextNode(separator));
                        }
                    });

                    const copyBtn = document.createElement('button');
                    copyBtn.classList.add('copy-btn');
                    copyBtn.title = 'Copiar nombres';
                    copyBtn.textContent = '📋';

                    row.appendChild(titleEl);
                    row.appendChild(namesEl);
                    row.appendChild(copyBtn);
                    assignmentsContainer.appendChild(row);
                });

                weekCard.innerHTML = `<h3>Semana ${week.week_index + 1} - ${week.week_date}</h3>`;
                weekCard.appendChild(assignmentsContainer);
                outputDiv.appendChild(weekCard);
            });

            // Añadir botón para guardar el programa
            const saveButton = document.createElement('button');
            saveButton.id = 'save-schedule-btn';
            saveButton.textContent = 'Guardar Programa en el Historial';
            outputDiv.appendChild(saveButton);

        } else {
            outputDiv.innerHTML = '<p>No se pudo generar el programa. Revisa la configuración y la lista de participantes.</p>';
        }
    }

    // --- Lógica del Modal de Override ---
    const modal = document.getElementById('manual-override-modal');
    const closeModalBtn = modal.querySelector('.close-btn');
    const modalTitle = document.getElementById('modal-assignment-title');
    const candidatesList = document.getElementById('modal-candidates-list');
    let activeAssigneeSpan = null;

    closeModalBtn.addEventListener('click', () => modal.classList.add('hidden'));
    window.addEventListener('click', (event) => {
        if (event.target == modal) modal.classList.add('hidden');
    });

    const scheduleOutput = document.getElementById('schedule-output');
    scheduleOutput.addEventListener('click', function(event) {
        // Abrir modal para cambio
        if (event.target.classList.contains('assignee')) {
            const targetSpan = event.target;
            activeAssigneeSpan = targetSpan;
            const { slotKey, weekIndex } = targetSpan.dataset;

            modalTitle.textContent = targetSpan.parentElement.previousElementSibling.textContent;
            candidatesList.innerHTML = '<li>Cargando...</li>';
            modal.classList.remove('hidden');

            // Fetch candidates for this slot
            fetch(`/api/candidates?slot_key=${slotKey}&week_index=${weekIndex}`)
                .then(res => res.json())
                .then(candidates => {
                    candidatesList.innerHTML = '';
                    if(candidates.length === 0) {
                        candidatesList.innerHTML = '<li>No hay otros candidatos disponibles.</li>';
                    }
                    candidates.forEach(c => {
                        const li = document.createElement('li');
                        li.textContent = c.nombre;
                        li.dataset.personId = c.persona_id;
                        li.addEventListener('click', () => {
                            activeAssigneeSpan.textContent = c.nombre;
                            activeAssigneeSpan.dataset.personId = c.persona_id;
                            modal.classList.add('hidden');
                        });
                        candidatesList.appendChild(li);
                    });
                });
        }

        // Copiar al portapapeles
        if (event.target.classList.contains('copy-btn')) {
            const names = event.target.previousElementSibling.textContent;
            navigator.clipboard.writeText(names).then(() => {
                const originalText = event.target.textContent;
                event.target.textContent = '¡Copiado!';
                setTimeout(() => { event.target.textContent = originalText; }, 1500);
            });
        }

        // Guardar programa
        if (event.target.id === 'save-schedule-btn') {
            const [year, month] = document.getElementById('month-input').value.split('-').map(Number);
            const scheduleData = { year, month, weeks: [] };

            document.querySelectorAll('.schedule-week').forEach(weekEl => {
                const weekIndex = parseInt(weekEl.querySelector('.assignee').dataset.weekIndex, 10);
                const weekData = { week_index: weekIndex, assignments: [] };

                weekEl.querySelectorAll('.assignment-row').forEach(rowEl => {
                    const assignmentData = {
                        title: rowEl.querySelector('.assignment-title').textContent.replace(':', ''),
                        slots: []
                    };
                    rowEl.querySelectorAll('.assignee').forEach(assigneeEl => {
                        assignmentData.slots.push({
                            person_id: assigneeEl.dataset.personId,
                            slot_key: assigneeEl.dataset.slotKey
                        });
                    });
                    weekData.assignments.push(assignmentData);
                });
                scheduleData.weeks.push(weekData);
            });

            fetch('/api/save_schedule', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(scheduleData)
            })
            .then(res => res.json())
            .then(result => {
                if (result.success) {
                    alert('¡Programa guardado con éxito!');
                    event.target.disabled = true;
                    event.target.textContent = 'Guardado';
                } else {
                    alert('Error al guardar el programa: ' + result.error);
                }
            });
        }
    });
});