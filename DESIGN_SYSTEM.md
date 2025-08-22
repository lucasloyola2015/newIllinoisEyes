# Sistema de Diseño - Illinois Eyes

## 🎨 Paleta de Colores Estandarizada

### Colores de Botones
- **PRIMARY** (`#d41414`): Acciones principales, guardar, aceptar
- **SECONDARY** (`#2a2a2f`): Acciones secundarias, cancelar, volver
- **SUCCESS** (`#28a745`): Confirmaciones, acciones exitosas
- **WARNING** (`#ffc107`): Advertencias, acciones de precaución
- **DANGER** (`#dc3545`): Eliminar, detener, acciones destructivas
- **INFO** (`#17a2b8`): Información, enlaces

### Variables CSS
```css
--btn-primary: #d41414;
--btn-secondary: #2a2a2f;
--btn-success: #28a745;
--btn-warning: #ffc107;
--btn-danger: #dc3545;
--btn-info: #17a2b8;
```

## 🔘 Sistema de Botones

### Clases Disponibles

#### Colores
- `.btn-primary` - Acciones principales
- `.btn-secondary` - Acciones secundarias
- `.btn-success` - Confirmaciones
- `.btn-warning` - Advertencias
- `.btn-danger` - Acciones destructivas
- `.btn-info` - Información

#### Tamaños
- `.btn-lg` - Botones grandes
- `.btn` - Botones estándar
- `.btn-sm` - Botones pequeños

#### Especiales
- `.btn-transparent` - Fondo transparente

### Ejemplos de Uso

```html
<!-- Botón principal -->
<button class="btn btn-primary">Guardar</button>

<!-- Botón secundario -->
<button class="btn btn-secondary">Cancelar</button>

<!-- Botón de confirmación -->
<button class="btn btn-success">Confirmar</button>

<!-- Botón de advertencia -->
<button class="btn btn-warning">Advertencia</button>

<!-- Botón de eliminación -->
<button class="btn btn-danger">Eliminar</button>

<!-- Botón pequeño -->
<button class="btn btn-sm btn-primary">Pequeño</button>

<!-- Botón grande -->
<button class="btn btn-lg btn-success">Grande</button>
```

## 📋 Convenciones de Nombres

### ✅ USAR
- `.btn-primary` para acciones principales
- `.btn-secondary` para acciones secundarias
- `.btn-success` para confirmaciones
- `.btn-warning` para advertencias
- `.btn-danger` para acciones destructivas
- `.btn-info` para información

### ❌ NO USAR (Deprecados)
- `.btn-red` → usar `.btn-danger`
- `.btn-learning` → usar `.btn-danger`
- `.btn-camera` → usar `.btn-secondary`
- `.btn-area` → usar `.btn-danger` (inactivo) / `.btn-success` (activo)

## 🎯 Casos de Uso Específicos

### Formularios
```html
<!-- Guardar formulario -->
<button class="btn btn-primary">Guardar</button>

<!-- Cancelar formulario -->
<button class="btn btn-secondary">Cancelar</button>

<!-- Restablecer formulario -->
<button class="btn btn-warning">Restablecer</button>
```

### Modales
```html
<!-- Confirmar acción -->
<button class="btn btn-primary">Aceptar</button>

<!-- Cancelar acción -->
<button class="btn btn-secondary">Cancelar</button>

<!-- Eliminar elemento -->
<button class="btn btn-danger">Eliminar</button>
```

### Control de Procesos
```html
<!-- Iniciar proceso -->
<button class="btn btn-success">Iniciar</button>

<!-- Pausar proceso -->
<button class="btn btn-warning">Pausar</button>

<!-- Detener proceso -->
<button class="btn btn-danger">Detener</button>
```

### Navegación
```html
<!-- Volver -->
<button class="btn btn-secondary">Volver</button>

<!-- Continuar -->
<button class="btn btn-primary">Continuar →</button>

<!-- Configurar -->
<button class="btn btn-info">Configurar</button>
```

## 🔧 Botones Especializados

### Navegación
- `.navbtn` - Botones de navegación principal
- `.navbtn.active` - Estado activo

### Pestañas
- `.tab-button` - Pestañas de configuración
- `.tab-button.active` - Pestaña activa

### Filtros
- `.filter-tab` - Pestañas de filtros
- `.filter-tab.active` - Filtro activo

### Configuración
- `.cfg-btn` - Botones grandes de configuración

## 📐 Jerarquía Visual

### Tamaños
1. **Grande** (`.btn-lg`): Configuraciones principales, acciones críticas
2. **Normal** (`.btn`): Acciones estándar, formularios
3. **Pequeño** (`.btn-sm`): Controles compactos, acciones secundarias

### Importancia
1. **Primario** (`.btn-primary`): Acción principal de la página
2. **Secundario** (`.btn-secondary`): Acciones de apoyo
3. **Éxito** (`.btn-success`): Confirmaciones positivas
4. **Advertencia** (`.btn-warning`): Acciones de precaución
5. **Peligro** (`.btn-danger`): Acciones destructivas

## 🎨 Estados de Botones

### Estados Básicos
- **Normal**: Color base
- **Hover**: Color más oscuro + elevación
- **Active**: Color más oscuro + sin elevación
- **Disabled**: Opacidad 50% + cursor not-allowed

### Estados Especiales
- **Loading**: Agregar spinner + disabled
- **Success**: Cambiar a `.btn-success` temporalmente
- **Error**: Cambiar a `.btn-danger` temporalmente

## 📱 Responsive Design

### Breakpoints
- **Mobile**: Botones full-width en formularios
- **Tablet**: Tamaño normal
- **Desktop**: Tamaño normal

### Adaptaciones
```css
@media (max-width: 768px) {
  .btn {
    width: 100%;
    margin-bottom: 8px;
  }
}
```

## 🔄 Migración de Código Existente

### Cambios Automáticos
- `.btn-red` → `.btn-danger`
- `.btn-learning` → `.btn-danger`
- `.btn-camera` → `.btn-secondary`
- `.btn-area` → `.btn-danger` (inactivo) / `.btn-success` (activo)

### Verificación Manual
1. Revisar todos los botones "Guardar" → usar `.btn-primary`
2. Revisar todos los botones "Cancelar" → usar `.btn-secondary`
3. Revisar todos los botones "Eliminar" → usar `.btn-danger`
4. Revisar todos los botones "Confirmar" → usar `.btn-success`

## 📝 Checklist para Nuevos Botones

- [ ] ¿Es una acción principal? → `.btn-primary`
- [ ] ¿Es una acción secundaria? → `.btn-secondary`
- [ ] ¿Es una confirmación? → `.btn-success`
- [ ] ¿Es una advertencia? → `.btn-warning`
- [ ] ¿Es una acción destructiva? → `.btn-danger`
- [ ] ¿Es información? → `.btn-info`
- [ ] ¿Necesita ser grande? → agregar `.btn-lg`
- [ ] ¿Necesita ser pequeño? → agregar `.btn-sm`
- [ ] ¿Tiene el texto correcto?
- [ ] ¿Tiene el icono correcto (si aplica)?

## 🎯 Principios de Diseño

1. **Consistencia**: Usar siempre las mismas clases para las mismas acciones
2. **Jerarquía**: El botón más importante debe ser el más prominente
3. **Accesibilidad**: Contraste adecuado y estados claros
4. **Feedback**: Estados hover y active claros
5. **Simplicidad**: Un botón = una acción

---

**Última actualización**: Diciembre 2024
**Versión**: 2.0
**Mantenedor**: Sistema de Diseño Illinois Eyes

