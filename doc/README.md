# SRS Addendum: TeXManager GNOME — Extended Feature Specifications

This addendum extends the original SRS with fully specified functional requirements and UI descriptions for the proposed additional features, organized by module.

Hierarchical breakdown:

- `Module_A_Inspection_Diagnostic/`
  - A.1 Log Parser / Error Triage
  - A.2 Package Dependency Resolver
  - A.3 Version Conflict Detector
- `Module_B_Onboarding_Installation/`
  - B.1 Custom Scheme Picker
  - B.2 Mirror Selection
  - B.3 Resume/Retry Logic
- `Module_C_Lifecycle_Management/`
  - C.1 Rollback/Snapshot Support
  - C.2 Scheduled Update Checks
- `Module_D_CTAN_Documentation/`
  - D.1 Bulk Package Operations
  - D.2 Explain This Package Panel
- `Module_E_Maintenance_Auxiliary/`
  - E.1 Project Templates
  - E.2 Bibliography Tool Integration
  - E.3 Symlink/PATH Doctor
- `New_Tab4_Compile_Watch/` — Tab 4: Compile & Watch
- `Cross_Cutting/`
  - X.1 Flatpak / Sandboxing Considerations
  - X.2 Consistent Undo/Confirmation Pattern

## Summary Table

| Module | New Feature | Complexity | Priority |
|---|---|---|---|
| A | Log Parser / Error Triage | Medium | High |
| A | Package Dependency Resolver | Medium | High |
| A | Version Conflict Detector | Low | Medium |
| B | Custom Scheme Picker | Low | Medium |
| B | Mirror Selection | Medium | Low |
| B | Resume/Retry Logic | Medium | Medium |
| C | Rollback/Snapshot Support | High | Medium |
| C | Scheduled Update Checks | Low | Low |
| D | Bulk Package Operations | Low | Medium |
| D | Explain This Package Panel | Low | Low |
| E | Project Templates | Low | High |
| E | Bibliography Tool Integration | Medium | Medium |
| E | Symlink/PATH Doctor | Low | Low |
| New | Tab 4: Compile & Watch | High | High |
| Cross | Flatpak Considerations | Medium | Medium |
| Cross | Undo/Confirmation Consistency | Low | High |
