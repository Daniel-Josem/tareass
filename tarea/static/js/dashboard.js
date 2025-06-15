document.addEventListener("DOMContentLoaded", function () {
  // --- Funciones para abrir y cerrar modales ---
  function abrirModal(modal) {
    modal.style.display = "block";
    setTimeout(() => modal.classList.add("modal-show"), 10);
  }

  function cerrarModal(modal) {
    modal.classList.remove("modal-show");
    modal.addEventListener("transitionend", () => {
      if (!modal.classList.contains("modal-show")) {
        modal.style.display = "none";
      }   
    }, { once: true });   
  }

  // --- Sidebar toggle ---
  const toggleButton = document.getElementById("btn-toggle-sidebar");
  const sidebar = document.getElementById("sidebar");

  if (toggleButton && sidebar) {
    toggleButton.addEventListener("click", () => sidebar.classList.toggle("collapsed"));
  }

  // --- Guardar ajustes ---
  const formAjustes = document.getElementById("formAjustes");
  if (formAjustes) {
    formAjustes.addEventListener("submit", function (e) {
      e.preventDefault();
      const formData = new FormData(formAjustes);
      const temaSeleccionado = formData.get("tema");
      const idiomaSeleccionado = formData.get("idioma");

      fetch("/ajustes", {
        method: "POST",
        body: formData,
      })
        .then(res => res.ok ? res.text() : Promise.reject("Error al guardar ajustes."))
        .then(() => {
          const mensaje = idiomaSeleccionado === "en" ? "Settings saved!" : "¡Ajustes guardados!";
          document.getElementById("mensajeAjustes").textContent = mensaje;

          if (temaSeleccionado === "oscuro") {
            document.body.classList.add("tema-oscuro");
          } else {
            document.body.classList.remove("tema-oscuro");
          }

          aplicarTraduccionGeneral(idiomaSeleccionado);

          const modal = bootstrap?.Modal.getInstance(document.getElementById("ajustesModal"));
          if (modal) modal.hide();
        })
        .catch(err => {
          document.getElementById("mensajeAjustes").textContent = err;
        });
    });
  }

  // --- Aplicar ajustes guardados desde backend ---
  fetch("/mis-ajustes")
    .then(res => res.json())
    .then(data => {
      if (data.tema === "oscuro") {
        document.body.classList.add("tema-oscuro");
      }
      aplicarTraduccionGeneral(data.idioma || "es");
    });

  // --- Traducciones ---
  function aplicarTraduccionGeneral(idioma) {
    const traducciones = {
      en: {
        ajustesModalLabel: "Account Settings",
        labelTema: "Theme",
        labelIdioma: "Language",
        labelNotificaciones: "Receive email notifications",
        btnCancelar: "Cancel",
        btnGuardar: "Save changes",
        navPlanificacion: "Planning",
        navCalendario: "Calendar",
        mensajeAjustes: "Settings saved!",
        tituloSidebar: "Task",
        linkProfesores: "My teachers",
        linkProyectos: "Projects",
        linkTareas: "Tasks",
      },
      es: {
        ajustesModalLabel: "Ajustes de cuenta",
        labelTema: "Tema",
        labelIdioma: "Idioma",
        labelNotificaciones: "Recibir notificaciones por correo",
        btnCancelar: "Cancelar",
        btnGuardar: "Guardar cambios",
        navPlanificacion: "Planificación",
        navCalendario: "Calendario",
        mensajeAjustes: "¡Ajustes guardados!",
        tituloSidebar: "Tarea",
        linkProfesores: "Mis profesores",
        linkProyectos: "Proyectos",
        linkTareas: "Tareas",
      },
    };

    const t = traducciones[idioma];
    if (!t) return;

    const ids = [
      "ajustesModalLabel",
      "labelTema",
      "labelIdioma",
      "labelNotificaciones",
      "btnCancelar",
      "btnGuardar",
      "navPlanificacion",
      "navCalendario",
      "tituloSidebar",
      "linkProfesores",
      "linkProyectos",
      "linkTareas",
    ];

    ids.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.innerText = t[id];
    });

    const mensaje = document.getElementById("mensajeAjustes");
    if (mensaje && mensaje.textContent) {
      mensaje.textContent = t["mensajeAjustes"];
    }
  }
  
  // --- Modal Profesor ---
  const profesorCard = document.querySelector(".Profesor");
  const modalProfesor = document.getElementById("modal-profesor");
  const cerrarBtnProfesor = document.getElementById("cerrar-profesor");

  if (profesorCard && modalProfesor && cerrarBtnProfesor) {
    profesorCard.addEventListener("click", () => abrirModal(modalProfesor));
    cerrarBtnProfesor.addEventListener("click", () => cerrarModal(modalProfesor));
    modalProfesor.addEventListener("click", (e) => {
      if (e.target === modalProfesor) cerrarModal(modalProfesor);
    });
  }

  // --- Modal Materia ---
  const materiaCard = document.querySelector(".Materia");
  const modalMateria = document.getElementById("modal-materia");
  const cerrarBtnMateria = document.getElementById("cerrar-materia");
  const formMateria = document.getElementById("formMateria");

  if (materiaCard && modalMateria && cerrarBtnMateria && formMateria) {
    materiaCard.addEventListener("click", () => abrirModal(modalMateria));
    cerrarBtnMateria.addEventListener("click", () => cerrarModal(modalMateria));
    window.addEventListener("click", (e) => {
      if (e.target === modalMateria) cerrarModal(modalMateria);
    });

    formMateria.addEventListener("submit", function (e) {
      e.preventDefault();
      const nombreMateria = this.nombre_materia.value.trim();
      const profesorMateria = this.profesor_materia.value.trim();

      if (!nombreMateria || !profesorMateria) {
        alert("Por favor llena todos los campos.");
        return;
      }

      alert(`Materia registrada:\nNombre: ${nombreMateria}\nProfesor: ${profesorMateria}`);
      cerrarModal(modalMateria);
      this.reset();
    });
  }

  // --- BLOQUE PARA DESPLEGAR / COLAPSAR “Cursos” ---
  const linkCursos = document.getElementById("link-cursos");
  const itemHasSubmenu = linkCursos?.closest(".has-submenu");

  if (linkCursos && itemHasSubmenu) {
    linkCursos.addEventListener("click", function (e) {
      e.preventDefault(); // Evita el comportamiento por defecto del enlace
      itemHasSubmenu.classList.toggle("open");
    });
  }

});``
